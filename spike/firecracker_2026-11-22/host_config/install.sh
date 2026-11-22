#!/bin/bash
# One-time, persistent host configuration for the spike. Run as root ON THE KVM HOST ONLY. NOT RUN by the author.
set -euo pipefail
H=$(cd "$(dirname "$0")" && pwd); S=$(cd "$H/.." && pwd)
getent group kvm >/dev/null || groupadd --system kvm
id plea-spike >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin -G kvm plea-spike
install -m 0644 "$H/99-plea-spike-kvm.rules" /etc/udev/rules.d/
install -m 0644 "$H/plea-spike-run@.service" /etc/systemd/system/
mkdir -p /opt/plea-spike /etc/plea-spike /var/lib/plea-spike
cp -a "$S/prereq.py" "$S/pins.json" "$S/harness" "$S/guest_image" /opt/plea-spike/
mkdir -p /opt/plea-spike/downloads; [ -f "$S/downloads/firecracker" ] && cp -a "$S/downloads/firecracker" /opt/plea-spike/downloads/
chown -R root:root /opt/plea-spike; chown plea-spike:plea-spike /var/lib/plea-spike
udevadm control --reload && udevadm trigger --name-match=kvm
systemctl daemon-reload
echo "installed. Run host_config/check_after_reboot.sh now and again after every reboot."
