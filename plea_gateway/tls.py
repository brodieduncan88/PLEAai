"""Transport security (v0.5): mutual TLS between the governor, the witness service and the gate host.

What it adds.  Until v0.4 the services spoke loopback HTTP: the signed receipts and reports proved what the witness
accepted and what the gate saw, but nothing authenticated a request or a server.  Now each service can present a
certificate from the deployment's own certificate authority and require one from every client; each client pins
that authority and presents its own certificate.  A request from a process without a certificate issued by the
pinned authority never reaches the handler; a server that is not the pinned one never receives the request.
An allow-list of client names (the certificate's common name) says which role may call which service.

The receipts and reports stay the end-to-end proof.  TLS protects the hop; it does not replace them.

    tls.py init DIR [--san 127.0.0.1,localhost] [--days 365]
        writes DIR/ca.crt ca.key, and for witness, host (server certificates) and governor (a client certificate)
        NAME.crt NAME.key.  Keep the .key files private; distribute ca.crt to every party.

Server:  TLSServer(cert, key, ca, allow=('governor',)).context()   requires a client certificate from `ca`
Client:  TLSClient(ca, cert, key).context()                        pins `ca`, checks the server's name, presents cert
"""
import argparse
import dataclasses
import datetime as dt
import ipaddress
import pathlib
import ssl

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


class TransportError(Exception):
    """TLS refused the exchange (no certificate, wrong authority, wrong name).  Retrying will not help."""


# ---------------------------------------------------------------------------------------------------- certificates
def _now():
    return dt.datetime.now(dt.timezone.utc)


def _key():
    return ec.generate_private_key(ec.SECP256R1())


def _pem_key(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def make_ca(name: str, days: int = 3650) -> tuple[bytes, bytes]:
    """A private certificate authority.  Returns (key_pem, cert_pem)."""
    key = _key(); subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(_now() - dt.timedelta(minutes=5))
            .not_valid_after(_now() + dt.timedelta(days=days))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False, key_agreement=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    return _pem_key(key), cert.public_bytes(serialization.Encoding.PEM)


def issue(ca_key_pem: bytes, ca_cert_pem: bytes, name: str, role: str, san=(), days: int = 365) -> tuple[bytes, bytes]:
    """A certificate for `name` signed by the authority.  role 'server' (with subject alternative names) or 'client'."""
    ca_key = serialization.load_pem_private_key(ca_key_pem, None); ca_cert = x509.load_pem_x509_certificate(ca_cert_pem)
    key = _key()
    b = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
         .issuer_name(ca_cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(_now() - dt.timedelta(minutes=5)).not_valid_after(_now() + dt.timedelta(days=days))
         .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True))
    if role == 'server':
        names = []
        for s in san:
            try:
                names.append(x509.IPAddress(ipaddress.ip_address(s)))
            except ValueError:
                names.append(x509.DNSName(s))
        b = b.add_extension(x509.SubjectAlternativeName(names), critical=False)
        b = b.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
    elif role == 'client':
        b = b.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
    else:
        raise ValueError(role)
    cert = b.sign(ca_key, hashes.SHA256())
    return _pem_key(key), cert.public_bytes(serialization.Encoding.PEM)


def init_pki(directory, san=('127.0.0.1', 'localhost'), days: int = 365, servers=('witness', 'host'), clients=('governor',),
             ca_name: str = 'plea-ca') -> dict:
    """Write a deployment's PKI into `directory`.  Returns the paths."""
    d = pathlib.Path(directory); d.mkdir(parents=True, exist_ok=True)
    ca_key, ca_cert = make_ca(ca_name)
    (d / 'ca.key').write_bytes(ca_key); (d / 'ca.crt').write_bytes(ca_cert)
    paths = {'ca': str(d / 'ca.crt'), 'ca_key': str(d / 'ca.key')}
    for name in servers:
        k, c = issue(ca_key, ca_cert, name, 'server', san, days); (d / f'{name}.key').write_bytes(k); (d / f'{name}.crt').write_bytes(c)
        paths[name] = (str(d / f'{name}.crt'), str(d / f'{name}.key'))
    for name in clients:
        k, c = issue(ca_key, ca_cert, name, 'client', (), days); (d / f'{name}.key').write_bytes(k); (d / f'{name}.crt').write_bytes(c)
        paths[name] = (str(d / f'{name}.crt'), str(d / f'{name}.key'))
    for p in d.glob('*.key'):
        p.chmod(0o600)
    return paths


# ---------------------------------------------------------------------------------------------------- contexts
@dataclasses.dataclass(frozen=True)
class TLSServer:
    cert: str
    key: str
    ca: str                                   # the authority whose client certificates are accepted; one file, possibly a bundle
    allow: tuple = ()                         # client common names admitted; empty admits every certificate the authority issued

    def context(self) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(self.cert, self.key)
        ctx.load_verify_locations(cafile=self.ca)
        ctx.verify_mode = ssl.CERT_REQUIRED               # no client certificate, no request
        return ctx


@dataclasses.dataclass(frozen=True)
class TLSClient:
    ca: str                                   # the authority the server must chain to (a file; a bundle during a CA rotation)
    cert: str | None = None
    key: str | None = None

    def context(self) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cafile=self.ca)
        if self.cert:
            ctx.load_cert_chain(self.cert, self.key)
        return ctx


def bundle(out: str, *ca_files: str) -> str:
    """Concatenate authorities into one file, for the overlap window of a CA rotation."""
    pathlib.Path(out).write_bytes(b''.join(pathlib.Path(f).read_bytes() for f in ca_files)); return out


def peer_common_name(cert: dict | None) -> str | None:
    if not cert:
        return None
    for rdn in cert.get('subject', ()):
        for k, v in rdn:
            if k == 'commonName':
                return v
    return None


def is_transport_error(exc: BaseException) -> bool:
    """True when an exception from urllib is TLS refusing the exchange: at the handshake, or on the first read under
    TLS 1.3, where the server's alert arrives after the client thinks the handshake is done.  A connection closed
    without a response is not one (amendment 1): the client cannot tell a service that died mid-request from plain
    HTTP spoken to a TLS port, and the former must be retried, so both stay WitnessUnavailable / ConnectionError."""
    if isinstance(exc, ssl.SSLError):
        return True
    return isinstance(getattr(exc, 'reason', None), ssl.SSLError)


class TLSHandlerMixin:
    """For BaseHTTPRequestHandler subclasses: the handshake in the handler's thread (never in the accept loop), the
    peer's name from its certificate, and the allow-list.  tls_allow is set on the class; () admits every certificate."""
    tls_allow: tuple = ()

    def setup(self):
        super().setup()
        self.peer_name, self.tls_failed = None, False
        if isinstance(self.connection, ssl.SSLSocket):
            try:
                self.connection.do_handshake()
            except (ssl.SSLError, OSError):
                self.tls_failed = True; return
            self.peer_name = peer_common_name(self.connection.getpeercert())

    def handle(self):
        if self.tls_failed:
            return
        super().handle()

    def peer_allowed(self) -> bool:
        if not isinstance(self.connection, ssl.SSLSocket) or not self.tls_allow:
            return True
        return self.peer_name in self.tls_allow


def wrap_server(server, tls: TLSServer | None):
    """Wrap an HTTPServer's listening socket; the handshake is deferred to the handler (TLSHandlerMixin.setup)."""
    if tls is None:
        return server
    server.socket = tls.context().wrap_socket(server.socket, server_side=True, do_handshake_on_connect=False)
    return server


def add_server_args(ap: argparse.ArgumentParser):
    ap.add_argument('--tls-cert'); ap.add_argument('--tls-key'); ap.add_argument('--tls-ca', help='the authority whose client certificates are accepted')
    ap.add_argument('--tls-allow', action='append', default=[], help='a client common name to admit; repeatable; none admits every certificate the authority issued')


def server_from_args(a) -> TLSServer | None:
    given = [a.tls_cert, a.tls_key, a.tls_ca]
    if not any(given):
        return None
    if not all(given):
        raise SystemExit('TLS needs all of --tls-cert, --tls-key and --tls-ca')
    return TLSServer(a.tls_cert, a.tls_key, a.tls_ca, tuple(a.tls_allow))


def add_client_args(ap: argparse.ArgumentParser):
    ap.add_argument('--tls-ca', help='the authority the services must chain to'); ap.add_argument('--tls-cert'); ap.add_argument('--tls-key')


def client_from_args(a) -> TLSClient | None:
    if not a.tls_ca:
        if a.tls_cert or a.tls_key:
            raise SystemExit('TLS needs --tls-ca')
        return None
    if bool(a.tls_cert) != bool(a.tls_key):
        raise SystemExit('--tls-cert and --tls-key go together')
    return TLSClient(a.tls_ca, a.tls_cert, a.tls_key)


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    i = sub.add_parser('init'); i.add_argument('dir'); i.add_argument('--san', default='127.0.0.1,localhost'); i.add_argument('--days', type=int, default=365)
    i.add_argument('--servers', default='witness,host'); i.add_argument('--clients', default='governor'); i.add_argument('--ca-name', default='plea-ca')
    a = ap.parse_args()
    paths = init_pki(a.dir, tuple(s for s in a.san.split(',') if s), a.days, tuple(a.servers.split(',')), tuple(a.clients.split(',')), a.ca_name)
    for k, v in paths.items():
        print(k, v if isinstance(v, str) else ' '.join(v))


if __name__ == '__main__':
    main()
