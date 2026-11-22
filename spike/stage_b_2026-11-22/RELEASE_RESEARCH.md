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
  - **Update, 22 November 2026 (after commit 2c1af26), at the owner's direction.** The line above is kept as it was
    written. The advisory below is recorded from the owner's statement. A separate AI agent's read-only audit
    (`verify/reviews/STAGEB_AUDIT_2C1AF26_2026-11-22.md`) checked it against two primary sources, and they agree.
  - **CVE-2026-122192.**
    - Authoritative advisory: AWS Security Bulletin 2026-169-AWS,
      `https://aws.amazon.com/security/security-bulletins/2026-169-aws/`. The agent read it only in summarised form;
      its fetch tool would not reproduce the full text.
    - CVE record: `https://cveawg.mitre.org/api/cve/CVE-2026-122192`, read in full. Assigner AMZN; published
      2026-11-04; CVSS 3.1 7.5; CWE-390 and CWE-825.
    - **The flaw.** Firecracker mishandles a failed memory remap. A guest user with root privileges might read or
      modify the VMM process's memory. The route is a balloon or virtio-mem discard request, on a microVM restored
      from a snapshot with the File memory backend, when the host fails to create the replacement mapping.
    - **Affected:** v0.23.0 through v1.16.1. **Fixed:** v1.16.2 and v1.17.0. The v1.17.0 CHANGELOG entry #6174
      is consistent with that.
    - **v1.18.0**, the release this bundle selects, **is outside the affected range.**
    - **Relevance to the proposed test configuration: none of the prerequisites is present.**
      - The VM configuration `fclib.py` writes (`vm.json`, lines 485-489) holds only a boot source, three drives
        and the machine config.
      - It restores no snapshot, uses no File memory backend, and configures no balloon and no virtio-mem device.
      - The VMM is started with `--no-api` where the binary offers it. Otherwise it gets an API socket inside its
        chroot that nothing in the bundle calls. Either way, no snapshot, balloon or memory-hotplug request is made.
      - (T05's "balloon" is a guest workload that allocates memory. It is not a virtio balloon device.)
    - **Not verified from here:** the GitHub advisory GHSA-48ww-rqpp-2mgm. GitHub returned 403 to this session.
  - **Two other 2026 Firecracker advisories** were found incidentally. By its stated range, neither affects v1.18.0:
    - CVE-2026-1386, a jailer symlink file overwrite, fixed in 1.14.1 and 1.13.2 (AWS bulletin 2026-003-AWS, read);
    - CVE-2026-5747, a virtio PCI out-of-bounds write, fixed in 1.14.4 and 1.15.1 (known from search results only).
  - **An unverified claim.** A secondary blog describes an "FC-03" io_uring seccomp-bypass chain; its citation could
    not be traced. Unverified.
  - **What this does not show.** Being outside one advisory's range says nothing about vulnerabilities not yet
    found or published. The full GitHub advisories list for the project could not be read from here, so it is not
    established that no other advisory covers v1.18.0. None of this shows that the bundle, the jailer configuration
    or the host is secure. The same audit found a HIGH host-file-overwrite defect in the bundle's own `fetch.py`
    (H1), which no Firecracker version would fix. No isolation claim exists until the declared experiments are run
    on a real KVM-capable machine.
  - **Effect on the bundle's hash.** This update changes the bundle. The declaration hash the audit gives for
    2c1af26 (`3218f01d…8d44`, 52 files) applies only to that commit.
- **Guest kernel and rootfs:**
  - Firecracker CI artifacts at `https://s3.amazonaws.com/spec.ccfc.min`, prefix
    `firecracker-ci/20261118-6d7cfa9c6b53-0/x86_64/`: `vmlinux-6.1.188`, `vmlinux-6.18.62` and
    `ubuntu-24.04.squashfs`.
  - No checksums are published for them. They are trusted on first use: the bundle hashes them and pins the hashes.
