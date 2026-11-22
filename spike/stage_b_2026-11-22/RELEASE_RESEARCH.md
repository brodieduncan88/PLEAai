# Firecracker release and provenance: research notes

22 November 2026. Gathered by an AI agent, web only. The release page, the GitHub API and the security advisories page
were refused from this environment (HTTP 403). Raw files and release assets were reachable. Verified means read or
computed here; inferred is marked.

- **Support policy (verified):** `https://raw.githubusercontent.com/firecracker-microvm/firecracker/main/docs/RELEASE_POLICY.md`.
  - The last two minor releases are patched, for up to a year.
  - The table on 22 November 2026: v1.18 (released 2026-11-09) and v1.17 are supported; v1.16 is supported until
    2026-12-03; v1.15 and older are not.
  - v1.12 ended on 2025-12-17.
- **The release chosen:** v1.18.0.
  - Asset: `https://github.com/firecracker-microvm/firecracker/releases/download/v1.18.0/firecracker-v1.18.0-x86_64.tgz`,
    7,606,252 bytes.
  - Published SHA-256: `1ac8eec866dd5eea14efecf6323e22b23eea24054545338a5b34bc5bca6623cd`, from the adjacent
    `.sha256.txt`; recomputed here, and it matches.
  - The SHA256SUMS inside the archive:

    | file | SHA-256 |
    | --- | --- |
    | `firecracker-v1.18.0-x86_64` | `b33f46cd6d88834cf6a4f8d184f08f219809c636236bffd286d233a60602a2ba` |
    | `jailer-v1.18.0-x86_64` | `ddadbaa15b5c942271a83b7040ca7259c8ccf92a9e08d44cce0b86fa407ba460` |
    | `seccomp-filter-v1.18.0-x86_64.json` | `e165d4a31f03c7e8398622fe11078f506f7e0191b7f9272c2d583274f3f51656` |
- **Signatures and provenance:**
  - None found. Guessed names (`.sig`, `.asc`, `.minisig`, `.sigstore.json`, `.intoto.jsonl`, an SBOM) returned 404.
    CHANGELOG.md and SECURITY.md mention no signing.
  - The checksum comes from the same origin as the archive, so it proves transfer integrity, not who published it.
  - Not checked: whether the git tag is signed, and GitHub artifact attestations. The bundle's fetch step records the
    tag's signature, if git can reach GitHub.
  - The strongest alternative is a rebuild from source at the tag, compared with the release binary. Not attempted.
- **Security advisories:** not determined, since the advisories page could not be reached. The tag's CHANGELOG mentions
  no CVE for 1.16 to 1.18. That is not proof that none exists, and it is to be checked from a machine that can reach
  it.
- **Guest kernel and rootfs:**
  - Firecracker CI artifacts at `https://s3.amazonaws.com/spec.ccfc.min`, prefix
    `firecracker-ci/20261118-6d7cfa9c6b53-0/x86_64/`: `vmlinux-6.1.188`, `vmlinux-6.18.62` and
    `ubuntu-24.04.squashfs`.
  - No checksums are published for them. They are trusted on first use: the bundle hashes them and pins the hashes.
