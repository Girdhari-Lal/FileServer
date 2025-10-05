import os
import json
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AS2Partner, AS2Agreement

AS2_CONFIG_DIR = r"E:\python\sftp_project\as2\config"

@receiver(post_save, sender=AS2Partner)
def write_partner_config(sender, instance: AS2Partner, **kwargs):
    partner_config = {
        "name": instance.name,
        "as2_id": instance.as2_id,
        "url": instance.url,
        "cert_file": os.path.basename(instance.cert_file) if instance.cert_file else None,
        "private_key_file": os.path.basename(instance.private_key_file) if instance.private_key_file else None,
    }
    path = os.path.join(AS2_CONFIG_DIR, f"partner_{instance.id}.json")
    with open(path, "w") as f:
        json.dump(partner_config, f, indent=4)


@receiver(post_save, sender=AS2Agreement)
def write_agreement_config(sender, instance: AS2Agreement, **kwargs):
    agreement_config = {
        "sender_id": instance.sender.as2_id,
        "receiver_id": instance.receiver.as2_id,
        "encryption": instance.encryption,
        "signature": instance.signature,
        "mic_algo": instance.mic_algo
    }
    path = os.path.join(AS2_CONFIG_DIR, f"agreement_{instance.id}.json")
    with open(path, "w") as f:
        json.dump(agreement_config, f, indent=4)
