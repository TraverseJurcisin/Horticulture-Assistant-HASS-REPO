"""Crypto utilities needed for tests.

Provides a tiny subset of the upstream ``acme.crypto_util`` module.
"""

from OpenSSL import crypto  # type: ignore[import-untyped]


def dump_pyopenssl_chain(chain: list[crypto.X509], filetype: int = crypto.FILETYPE_PEM) -> bytes:
    """Dump a list of certificates into a single bundle.

    :param chain: Certificates to bundle (``OpenSSL.crypto.X509`` instances).
    :param filetype: Encoding format of the dumped certificates.
    :returns: Concatenated certificate chain.
    """
    return b"".join(crypto.dump_certificate(filetype, cert) for cert in chain)
