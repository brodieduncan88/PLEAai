"""A helper with an innocent name that reaches the CAP-KEY signer: only the dynamic guard can see it."""


def make_report(tc, root):
    s = tc.capkey_signer()
    return s.fence(root, 'a')
