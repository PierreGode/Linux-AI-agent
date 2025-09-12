# Linux Troubleshooting Scenarios

A reference list of diverse issues the agent should be prepared to handle.

1. apt update fails due to network unreachable
2. apt upgrade fails because a lock file is held by another process
3. apt install fails due to missing GPG key
4. apt update returns 404 for a repository
5. dpkg interrupted; requires `dpkg --configure -a`
6. apt install fails because the disk is full
7. apt-get cannot resolve hostnames due to DNS failure
8. pip install fails because GCC is missing
9. pip install fails due to SSL certificate verification error
10. pip install fails because of insufficient permissions
11. Filesystem is read-only, preventing writes
12. /root partition is 100% full
13. Process killed by OOM killer
14. Swap space absent causing memory pressure issues
15. Permission denied when accessing /var/log
16. Service fails to start due to missing configuration file
17. systemd service fails because ExecStart path is incorrect
18. Network interface (e.g., eth0) is down
19. Firewall blocking outbound HTTP traffic
20. SSH connection refused on port 22
21. SSH authentication fails due to wrong key
22. Cron job not executing because of incorrect path
23. Crontab uses wrong shell
24. NTP time drift causes certificate validation errors
25. Host unreachable due to misconfigured default gateway
26. DNS configuration points to invalid nameserver
27. Docker daemon is not running
28. Docker container fails to start because port is already in use
29. Docker pull fails due to rate limits
30. Docker build fails because Dockerfile is missing
31. Docker build fails due to missing dependency in container
32. Docker volume mount path does not exist
33. Docker container cannot resolve hostnames due to network issues
34. docker-compose command not found
35. Missing kernel module causes service failure
36. iptables rules block required traffic
37. ufw blocks port 80
38. TCP port open but service does not respond
39. SELinux prevents service from binding to port
40. sudoers misconfiguration locks out user
41. Environment variable not set causing script failure
42. Python script fails due to missing module
43. Executable not found in PATH
44. Broken symbolic link causes command failure
45. Package version mismatch leads to dependency errors
46. GPU not detected by driver
47. USB device unrecognized due to missing kernel module
48. Filesystem corruption requires fsck
49. Initramfs missing modules causing boot failure
50. Log rotation fails, causing large log files

51. Docker container cannot reach external network due to missing default route
52. Docker container port published but host firewall blocks access

