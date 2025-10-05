from celery import shared_task
from django.conf import settings
import json, time, logging, subprocess, os, sys 
from core.models import TaskLog, Script
from django.utils import timezone
from pathlib import Path
logger = logging.getLogger(__name__)

BASE_VENV_DIR = os.path.join(os.getcwd(), "venvs")

@shared_task(bind=True) 
def dynamic_task(self, **kwargs):
    logs = [] 
    base_dir = Path(settings.BASE_DIR)
    config_type = kwargs.get("config_type")
    if not config_type or config_type.lower() not in ["ftp", "sftp"]:
        raise ValueError("Invalid or missing config_type. Must be 'ftp' or 'sftp'.")
    config_type = config_type.lower()
    jar_name = f"{config_type}-0.0.1-SNAPSHOT.jar"
    jar_path = base_dir / jar_name
    if not jar_path.exists():
        raise FileNotFoundError(f"JAR file not found: {jar_path}")
    cmd = [
        "java", "-jar", jar_path,  
        kwargs["host"],        
        str(kwargs["port"]),    
        kwargs["username"],     
        kwargs["password"],    
        kwargs["remote_dir"],  
        kwargs["local_dir"],
        kwargs["operation"],      
    ]
    started_at = timezone.now()
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)       
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                log = json.loads(line)
                logs.append(f"[{log['level']}] {log['message']}")
                logger.info(f"LEVEL: {log['level']} MESSAGE: {log['message']}")
            except json.JSONDecodeError:
                logs.append(line)
                logger.info(f"RAW: {line}")
        for line in process.stderr:
            line = line.strip()
            if line:
                logs.append(f"[STDERR] {line}")
                logger.error(f"[PID {self.request.id}] {line}")
        process.wait()
        if process.returncode == 0:
            final_msg = f"operation succeeded for {kwargs['host']}:{kwargs['port']}"
            status = "SUCCESS"
        else:
            final_msg = f"operation failed with exit code {process.returncode}"
            status = "FAILED"
        logs.append(final_msg)
    except Exception as ex:
        final_msg = f"Python error while running JAR: {ex}"
        status = "FAILED"
        logs.append(final_msg)
        logger.exception(final_msg)
    ended_at = timezone.now()
    task_label = kwargs.get("periodic_name", self.name)
    TaskLog.objects.create(
        process_id=self.request.id,
        task_name=task_label,
        status=status,
        message="\n".join(logs),
        ended_at=ended_at,
        started_at=started_at
    )
    return {
        "process_id": self.request.id,
        "status": status,
        "message": final_msg
    }

def create_virtual_env(script_name):
    venv_dir = os.path.join(BASE_VENV_DIR, script_name)
    if not os.path.exists(venv_dir):
        os.makedirs(os.path.dirname(venv_dir), exist_ok=True)
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
    return venv_dir

def install_libraries(venv_path, libraries):
    if not libraries:
        return
    pip_path = (
        os.path.join(venv_path, "Scripts", "pip")
        if os.name == "nt"
        else os.path.join(venv_path, "bin", "pip")
    )

    # user may give "pip install pandas numpy"
    parts = libraries.strip().split()
    if parts[0].lower() == "pip" and parts[1].lower() == "install":
        libs = parts[2:]  # everything after "pip install"
    else:
        # fallback: assume space-separated libs
        libs = libraries.split()

    if libs:
        subprocess.check_call([pip_path, "install", "--default-timeout=1000"] + libs)


@shared_task(bind=True)
def run_script_task(self, **kwargs):
    try:
        script = Script.objects.get(name=kwargs["name"])
    except Script.DoesNotExist:
        return {"error": f"Script with name '{kwargs['name']}' does not exist."}
    venv_path = create_virtual_env(script.name)
    install_libraries(venv_path, script.required_libraries)
    python_path = (
        os.path.join(venv_path, "Scripts", "python")
        if os.name == "nt"
        else os.path.join(venv_path, "bin", "python")
    )
    script_path = script.file_path  # <-- use path stored in DB
    if not script_path or not os.path.exists(script_path):
        return {"error": f"Script file not found at {script_path}"}
    try:
        process = subprocess.Popen(
            [python_path, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        return {
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except Exception as e:
        return {"error": str(e)}
