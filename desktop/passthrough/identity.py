# SPDX-License-Identifier: GPL-3.0-only
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import os
from pathlib import Path
import secrets

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def private_write(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(data)


class Identity:
    """Private desktop identity. Never included in source or exported diagnostics."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.cert = self.directory/'certificate.pem'
        self.key = self.directory/'private-key.pem'
        if self.cert.exists() != self.key.exists():
            raise RuntimeError('Incomplete identity: preserve the files and choose a new identity directory')
        if not self.cert.exists():
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'PassThrough desktop')])
            now = datetime.now(timezone.utc)
            cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                    .public_key(key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=365))
                    .add_extension(x509.SubjectAlternativeName([
                        x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), False)
                    .sign(key, hashes.SHA256()))
            private_write(self.key, key.private_bytes(serialization.Encoding.PEM,
                          serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            private_write(self.cert, cert.public_bytes(serialization.Encoding.PEM))
        cert = x509.load_pem_x509_certificate(self.cert.read_bytes())
        if cert.not_valid_after_utc <= datetime.now(timezone.utc):
            raise RuntimeError('Desktop certificate expired; create a new identity and verify its new fingerprint on the phone')
        self.fingerprint = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
        # A fresh token for each launch; it is intentionally not persisted or logged.
        self.token = secrets.token_hex(32)
