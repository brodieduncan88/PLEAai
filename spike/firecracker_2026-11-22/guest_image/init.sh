#!/bin/sh
# /sbin/init of the guest. Runs one job selected by kernel cmdline spike.job=NAME, prints markers on the serial
# console, then reboots immediately (reboot=k makes Firecracker exit on x86).
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
mount -t proc proc /proc; mount -t sysfs sys /sys; mount -t devtmpfs dev /dev 2>/dev/null
mount -t tmpfs tmpfs /tmp
job=$(sed -n 's/.*spike\.job=\([^ ]*\).*/\1/p' /proc/cmdline)
nofile=$(sed -n 's/.*spike\.nofile=\([^ ]*\).*/\1/p' /proc/cmdline)
[ -n "$nofile" ] && ulimit -n "$nofile"
case "$job" in workload|sleep|forkbomb|membloat|fdexhaust|mmapexhaust|fdmmap) ;; *) echo "SPIKE_BAD_JOB"; job="" ;; esac
echo "SPIKE_BEGIN $job"
[ -n "$job" ] && timeout 120 python3 -I -B "/opt/spike/jobs/$job.py"
echo "SPIKE_END rc=$?"
echo b > /proc/sysrq-trigger
