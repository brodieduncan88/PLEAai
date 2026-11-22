#!/bin/bash
# Run as root on the KVM host after install and after EVERY reboot. Exit non-zero on any failure. NOT RUN by the author.
fail=0; ok(){ echo "OK    $*"; }; bad(){ echo "FAIL  $*"; fail=1; }
[ -c /dev/kvm ] && ok "/dev/kvm present" || bad "/dev/kvm missing (nested virt / instance type?)"
[ "$(stat -c '%G %a' /dev/kvm 2>/dev/null)" = "kvm 660" ] && ok "/dev/kvm group kvm mode 660" || bad "/dev/kvm perms: $(stat -c '%G %a' /dev/kvm 2>&1)"
id -nG plea-spike 2>/dev/null | tr ' ' '\n' | grep -qx kvm && ok "plea-spike in group kvm" || bad "plea-spike not in kvm group"
[ "$(stat -f -c %T /sys/fs/cgroup)" = cgroup2fs ] && ok "cgroup v2 unified" || bad "cgroup not v2 ($(stat -f -c %T /sys/fs/cgroup))"
grep -qw memory /sys/fs/cgroup/cgroup.controllers && grep -qw pids /sys/fs/cgroup/cgroup.controllers && grep -qw cpu /sys/fs/cgroup/cgroup.controllers && ok "root controllers memory pids cpu" || bad "controllers missing: $(cat /sys/fs/cgroup/cgroup.controllers)"
[ -f /etc/systemd/system/plea-spike-run@.service ] && ok "unit installed" || bad "unit missing"
[ "$(systemctl show -p Delegate --value plea-spike-run@x.service 2>/dev/null)" = yes ] && ok "Delegate=yes effective" || bad "Delegate not yes"
[ -f /etc/udev/rules.d/99-plea-spike-kvm.rules ] && ok "udev rule installed" || bad "udev rule missing"
echo "--- prereq.py as the service user inside a delegated cgroup ---"
systemd-run --quiet --wait --collect --pipe -p User=plea-spike -p SupplementaryGroups=kvm -p Delegate=yes \
  -E PLEA_SPIKE_HOME=/opt/plea-spike /usr/bin/python3 -I /opt/plea-spike/prereq.py \
  --firecracker /opt/plea-spike/downloads/firecracker --kernel /opt/plea-spike/guest_image/out/vmlinux \
  --rootfs /opt/plea-spike/guest_image/out/rootfs.ext4 --pins /opt/plea-spike/pins.json && ok "prereq.py all met" || bad "prereq.py NOT MET"
exit $fail
