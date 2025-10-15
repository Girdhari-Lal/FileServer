from celery import shared_task
from django.conf import settings
import json, logging, subprocess, os, sys 
from core.models import TaskLog, Script
from django.utils import timezone
from pathlib import Path
from django_celery_beat.models import PeriodicTask
from celery import shared_task, chain, signature, Celery

logger = logging.getLogger(__name__)
BASE_VENV_DIR = os.path.join(os.getcwd(), "venvs")
app = Celery(broker='redis://localhost:6379/0')

def safe_execute(func):
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return {"status": "success", "data": result}
        except Exception as e:
            logger.exception(f"Error in task {func.__name__}: {e}")
            return {"status": "failed", "error": str(e)}
    return wrapper

@app.task(bind=True, name="core.tasks.dynamic_task")
@safe_execute
def dynamic_task(self, *args, **kwargs):
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
        "message": logs,
        "task_name":task_label
    }

@app.task(bind=True)
def email_jar_schedule(self, data=None, **kwargs):
    base_dir = Path(settings.BASE_DIR)
    jar_path = base_dir / "email-sender-0.0.1-SNAPSHOT.jar"

    if not jar_path.exists():
        logger.error(f"JAR file not found: {jar_path}")
        raise FileNotFoundError(f"JAR file not found: {jar_path}")
    if data and "data" in data:
        data = data["data"]
    files = data.get("files") if data else []
    attached_files = ", ".join(files) if files else "No files"
    
    process_id = data.get("process_id")
    logs = "\n".join(data.get("message", []))

    subject = f"{kwargs.get('subject', 'Task Update')} | Process ID: {process_id}"
    body = f"{kwargs.get('message_body', '')}\n\nTask Logs:\n{logs}"

    cmd = [
        "java", "-jar", str(jar_path),
        f"--host={kwargs.get('host')}",
        f"--port={kwargs.get('port')}",
        f"--tls={'true' if kwargs.get('tls') else 'false'}",
        f"--user={kwargs.get('user')}",
        f"--pass={kwargs.get('password')}",
        f"--to={kwargs.get('to_str')}",
        f"--subject={subject}",
        f"--body={body}",
        f"--attach={attached_files}", 
    ]
    logger.info(f"Executing command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info(f"Process finished with code {result.returncode}")
    if result.stdout:
        logger.debug(f"STDOUT: {result.stdout.strip()}")
    if result.stderr:
        logger.error(f"STDERR: {result.stderr.strip()}")
    status = "success" if result.returncode == 0 else "failed"
    return {
        "process_id": getattr(self.request, "id", None),
        "returncode": result.returncode,
        "status": status,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }

@app.task(bind=True, name="core.tasks.pick_file_task")
@safe_execute
def pick_file_task(self):
    base_dir = Path(settings.BASE_DIR)
    folder = base_dir / "download_file"
    files = [str(f) for f in folder.glob("*") if f.is_file()]
    if not files:
        raise FileNotFoundError("No files found in download_file folder")
    return {"process_id": self.request.id, "status": "success", "files": files}


# def send_email_via_jar(taskname, message, email_conn):
#     base_dir = Path(settings.BASE_DIR)
#     jar_path = base_dir / "email-sender-0.0.1-SNAPSHOT.jar"
#     if not jar_path.exists():
#         raise FileNotFoundError(f"JAR file not found: {jar_path}")
#     to_list = email_conn.to if isinstance(email_conn.to, list) else [email_conn.to]
#     to_str = ",".join(to_list)
#     cmd = [
#         "java", "-jar", str(jar_path),
#         f"--host={email_conn.host}",
#         f"--port={email_conn.port}",
#         f"--tls={'true' if email_conn.tls else 'false'}",
#         f"--user={email_conn.user}",
#         f"--pass={email_conn.password}",
#         f"--to={to_str}",
#         f"--subject={taskname} {email_conn.subject}",
#         f"--body={email_conn.message}\n{message}",
#     ]
#     if getattr(email_conn, "attachments", None):
#         for file_path in email_conn.attachments:
#             if Path(file_path).exists():
#                 cmd.append(f"--attach={file_path}")

#     result = subprocess.run(cmd, capture_output=True, text=True)
#     return {
#         "returncode": result.returncode,
#         "stdout": result.stdout.strip(),
#         "stderr": result.stderr.strip(),
#     }

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
    parts = libraries.strip().split()
    if parts[0].lower() == "pip" and parts[1].lower() == "install":
        libs = parts[2:] 
    else:
        libs = libraries.split()
    if libs:
        subprocess.check_call([pip_path, "install", "--default-timeout=1000"] + libs)

@app.task(bind=True, name="core.tasks.run_script_task")
@safe_execute
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

@shared_task(bind=True)
def orchestrator_chain_task(self, **kwargs):
    task_names = kwargs.get("task_names", [])
    if not task_names:
        raise ValueError("No task names provided in kwargs['task_names'].")
    task_signatures = []
    for name in task_names:
        try:
            ptask = PeriodicTask.objects.get(name=name)
        except PeriodicTask.DoesNotExist:
            raise ValueError(f"PeriodicTask '{name}' not found.")
        if not ptask.task:
            raise ValueError(f"PeriodicTask '{name}' has no task defined.")
        task_kwargs = json.loads(ptask.kwargs or "{}")
        sig = signature(ptask.task, kwargs=task_kwargs)
        task_signatures.append(sig)

    if not task_signatures:
        raise ValueError("No valid tasks to chain.")
    workflow = chain(*task_signatures)
    result = workflow.apply_async()
    return {
        "status": "Chain started",
        "chain_id": result.id,
        "tasks": task_names,
    }
