import hashlib
import unittest

import probe


class GameSpyAccountTests(unittest.TestCase):
    def test_client_and_server_proofs_swap_challenges(self):
        password_hash = hashlib.md5(b"example-password").hexdigest()
        user = "pilot@example.invalid"
        server_challenge = "abcdefghij"
        client_challenge = "0123456789abcdefghijklmnopqrstuv"

        client_proof = probe._gp_proof(
            password_hash, user, server_challenge, client_challenge
        )
        server_proof = probe._gp_proof(
            password_hash, user, client_challenge, server_challenge
        )

        self.assertEqual(len(client_proof), 32)
        self.assertEqual(len(server_proof), 32)
        self.assertNotEqual(client_proof, server_proof)

    def test_new_user_response_uses_nur_command(self):
        response = probe._gs_build(nur="", userid="1", profileid="1", id="1")
        self.assertEqual(
            response,
            b"\\nur\\\\userid\\1\\profileid\\1\\id\\1\\final\\",
        )

    def test_sfc3_legacy_proof_variant(self):
        password_hash = hashlib.md5(b"example-password").hexdigest()
        proof = probe._gp_proof(
            password_hash,
            "pilot@example.invalid",
            "abcdefghij",
            "0123456789abcdefghijklmnopqrstuv",
            spaces=40,
            include_user=False,
        )

        self.assertEqual(len(proof), 32)
        self.assertNotEqual(
            proof,
            probe._gp_proof(
                password_hash,
                "pilot@example.invalid",
                "abcdefghij",
                "0123456789abcdefghijklmnopqrstuv",
            ),
        )


if __name__ == "__main__":
    unittest.main()
