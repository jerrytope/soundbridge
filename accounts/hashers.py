"""Password hasher for accounts created by server/backend.js.

The Node server stored `salt:scrypt-hex`, using Node's default scrypt
parameters (N=16384, r=8, p=1) and a 64-byte derived key. Supporting that
format here means the accounts already in .data/soundbridge.sqlite can sign in
after import without a password reset. New passwords use Django's default
PBKDF2 hasher; a legacy hash is upgraded on the owner's next successful login.
"""
import hashlib

from django.contrib.auth.hashers import BasePasswordHasher, constant_time_compare
from django.utils.crypto import get_random_string

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = 64


def derive(password: str, salt: str) -> str:
    return hashlib.scrypt(
        password.encode('utf-8'),
        salt=salt.encode('utf-8'),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_LENGTH,
        maxmem=64 * 1024 * 1024,
    ).hex()


class NodeScryptPasswordHasher(BasePasswordHasher):
    algorithm = 'node-scrypt'

    def salt(self):
        return get_random_string(32, '0123456789abcdef')

    def encode(self, password, salt):
        return f'{self.algorithm}${salt}${derive(password, salt)}'

    def decode(self, encoded):
        algorithm, salt, digest = encoded.split('$', 2)
        assert algorithm == self.algorithm
        return {'algorithm': algorithm, 'salt': salt, 'hash': digest}

    def verify(self, password, encoded):
        decoded = self.decode(encoded)
        return constant_time_compare(derive(password, decoded['salt']), decoded['hash'])

    def safe_summary(self, encoded):
        decoded = self.decode(encoded)
        return {
            'algorithm': decoded['algorithm'],
            'salt': decoded['salt'][:6] + '...',
            'hash': decoded['hash'][:6] + '...',
        }

    def harden_runtime(self, password, encoded):
        pass


def from_node(stored: str) -> str:
    """Convert a Node `salt:hex` value into this hasher's encoded form."""
    salt, _, digest = stored.partition(':')
    return f'{NodeScryptPasswordHasher.algorithm}${salt}${digest}'
