[
    {
        "Id": "32b8ea3532767f98647392629586daf4a822ea90411ffa0755ec0af9fe63d2ba",
        "Created": "2024-06-26T13:38:00.725376251Z",
        "Path": "docker-entrypoint.sh",
        "Args": [
            "mysqld"
        ],
        "State": {
            "Status": "running",
            "Running": true,
            "Paused": false,
            "Restarting": false,
            "OOMKilled": false,
            "Dead": false,
            "Pid": 51374,
            "ExitCode": 0,
            "Error": "",
            "StartedAt": "2024-06-26T13:38:01.444945752Z",
            "FinishedAt": "0001-01-01T00:00:00Z",
            "Health": {
                "Status": "healthy",
                "FailingStreak": 0,
                "Log": [
                    {
                        "Start": "2024-06-26T14:20:50.541598469Z",
                        "End": "2024-06-26T14:20:50.616155761Z",
                        "ExitCode": 0,
                        "Output": "\u0007mysqladmin: connect to server at 'localhost' failed\nerror: 'Access denied for user 'root'@'localhost' (using password: NO)'\n"
                    },
                    {
                        "Start": "2024-06-26T14:21:00.619233501Z",
                        "End": "2024-06-26T14:21:00.661613668Z",
                        "ExitCode": 0,
                        "Output": "\u0007mysqladmin: connect to server at 'localhost' failed\nerror: 'Access denied for user 'root'@'localhost' (using password: NO)'\n"
                    },
                    {
                        "Start": "2024-06-26T14:21:10.664735464Z",
                        "End": "2024-06-26T14:21:10.729090839Z",
                        "ExitCode": 0,
                        "Output": "\u0007mysqladmin: connect to server at 'localhost' failed\nerror: 'Access denied for user 'root'@'localhost' (using password: NO)'\n"
                    },
                    {
                        "Start": "2024-06-26T14:21:20.730533469Z",
                        "End": "2024-06-26T14:21:20.785634094Z",
                        "ExitCode": 0,
                        "Output": "\u0007mysqladmin: connect to server at 'localhost' failed\nerror: 'Access denied for user 'root'@'localhost' (using password: NO)'\n"
                    },
                    {
                        "Start": "2024-06-26T14:21:30.788925126Z",
                        "End": "2024-06-26T14:21:30.839608168Z",
                        "ExitCode": 0,
                        "Output": "\u0007mysqladmin: connect to server at 'localhost' failed\nerror: 'Access denied for user 'root'@'localhost' (using password: NO)'\n"
                    }
                ]
            }
        },
        "Image": "sha256:e68e2614955cad9955f5bf3eab032c5c5356e00ae1e7725e850cc0beec446214",
        "ResolvConfPath": "/var/lib/docker/containers/32b8ea3532767f98647392629586daf4a822ea90411ffa0755ec0af9fe63d2ba/resolv.conf",
        "HostnamePath": "/var/lib/docker/containers/32b8ea3532767f98647392629586daf4a822ea90411ffa0755ec0af9fe63d2ba/hostname",
        "HostsPath": "/var/lib/docker/containers/32b8ea3532767f98647392629586daf4a822ea90411ffa0755ec0af9fe63d2ba/hosts",
        "LogPath": "/var/lib/docker/containers/32b8ea3532767f98647392629586daf4a822ea90411ffa0755ec0af9fe63d2ba/32b8ea3532767f98647392629586daf4a822ea90411ffa0755ec0af9fe63d2ba-json.log",
        "Name": "/keep-keep-database-1",
        "RestartCount": 0,
        "Driver": "overlay2",
        "Platform": "linux",
        "MountLabel": "",
        "ProcessLabel": "",
        "AppArmorProfile": "",
        "ExecIDs": null,
        "HostConfig": {
            "Binds": null,
            "ContainerIDFile": "",
            "LogConfig": {
                "Type": "json-file",
                "Config": {}
            },
            "NetworkMode": "keep_default",
            "PortBindings": {
                "3306/tcp": [
                    {
                        "HostIp": "",
                        "HostPort": "3306"
                    }
                ]
            },
            "RestartPolicy": {
                "Name": "no",
                "MaximumRetryCount": 0
            },
            "AutoRemove": false,
            "VolumeDriver": "",
            "VolumesFrom": null,
            "ConsoleSize": [
                0,
                0
            ],
            "CapAdd": null,
            "CapDrop": null,
            "CgroupnsMode": "private",
            "Dns": null,
            "DnsOptions": null,
            "DnsSearch": null,
            "ExtraHosts": [],
            "GroupAdd": null,
            "IpcMode": "private",
            "Cgroup": "",
            "Links": null,
            "OomScoreAdj": 0,
            "PidMode": "",
            "Privileged": false,
            "PublishAllPorts": false,
            "ReadonlyRootfs": false,
            "SecurityOpt": null,
            "UTSMode": "",
            "UsernsMode": "",
            "ShmSize": 67108864,
            "Runtime": "runc",
            "Isolation": "",
            "CpuShares": 0,
            "Memory": 0,
            "NanoCpus": 0,
            "CgroupParent": "",
            "BlkioWeight": 0,
            "BlkioWeightDevice": null,
            "BlkioDeviceReadBps": null,
            "BlkioDeviceWriteBps": null,
            "BlkioDeviceReadIOps": null,
            "BlkioDeviceWriteIOps": null,
            "CpuPeriod": 0,
            "CpuQuota": 0,
            "CpuRealtimePeriod": 0,
            "CpuRealtimeRuntime": 0,
            "CpusetCpus": "",
            "CpusetMems": "",
            "Devices": null,
            "DeviceCgroupRules": null,
            "DeviceRequests": null,
            "MemoryReservation": 0,
            "MemorySwap": 0,
            "MemorySwappiness": null,
            "OomKillDisable": null,
            "PidsLimit": null,
            "Ulimits": null,
            "CpuCount": 0,
            "CpuPercent": 0,
            "IOMaximumIOps": 0,
            "IOMaximumBandwidth": 0,
            "Mounts": [
                {
                    "Type": "volume",
                    "Source": "keep_mysql-data",
                    "Target": "/var/lib/mysql",
                    "VolumeOptions": {}
                }
            ],
            "MaskedPaths": [
                "/proc/asound",
                "/proc/acpi",
                "/proc/kcore",
                "/proc/keys",
                "/proc/latency_stats",
                "/proc/timer_list",
                "/proc/timer_stats",
                "/proc/sched_debug",
                "/proc/scsi",
                "/sys/firmware",
                "/sys/devices/virtual/powercap"
            ],
            "ReadonlyPaths": [
                "/proc/bus",
                "/proc/fs",
                "/proc/irq",
                "/proc/sys",
                "/proc/sysrq-trigger"
            ]
        },
        "GraphDriver": {
            "Data": {
                "LowerDir": "/var/lib/docker/overlay2/cabbc0c530aea7c9dd70d4bf2365f90a061715bf80c43da6560d86c8231f330b-init/diff:/var/lib/docker/overlay2/e7a2dc709b2bb4d880ade07741e5b7c4c757f7b3087d425a07a837b9687a3b37/diff:/var/lib/docker/overlay2/e1d3f350d8ebcd219de28891f8655b37c3b3f0bedbee70b458715c5a30973a78/diff:/var/lib/docker/overlay2/e657db02b9ae952f41f57c008c82ebbf14c275a0b6f2b69fcfaf86240d08f84a/diff:/var/lib/docker/overlay2/e544440da3d36c610052c27b6b828211b63a4fb3f3edb6506e256268fca83fed/diff:/var/lib/docker/overlay2/f4dfb5af5fb8c96c18b10df18fe10eb1d55584c870f0538a90057cd1fbf10883/diff:/var/lib/docker/overlay2/8768203707f378162d27a408ff1e65202c251859806c437fb6eb063786c66f9f/diff:/var/lib/docker/overlay2/425c2ef3ed330ae46686b0fd359b3a2c69470e028c6f7eb7e6a5dee5ad028c0f/diff:/var/lib/docker/overlay2/d9bef5374dcc03ccd8e88804887c33d7aa17c9f3603a2e904e07e60f192f7c29/diff:/var/lib/docker/overlay2/19fc03f4c95353879b4e1e2e7a7a175c7ef78fbd93df2a9bcd319530253774a4/diff:/var/lib/docker/overlay2/ffe5b52a0abd0bd3ae8d9e7940390491cd8d25b811f579f28492c272e2a2506c/diff",
                "MergedDir": "/var/lib/docker/overlay2/cabbc0c530aea7c9dd70d4bf2365f90a061715bf80c43da6560d86c8231f330b/merged",
                "UpperDir": "/var/lib/docker/overlay2/cabbc0c530aea7c9dd70d4bf2365f90a061715bf80c43da6560d86c8231f330b/diff",
                "WorkDir": "/var/lib/docker/overlay2/cabbc0c530aea7c9dd70d4bf2365f90a061715bf80c43da6560d86c8231f330b/work"
            },
            "Name": "overlay2"
        },
        "Mounts": [
            {
                "Type": "volume",
                "Name": "keep_mysql-data",
                "Source": "/var/lib/docker/volumes/keep_mysql-data/_data",
                "Destination": "/var/lib/mysql",
                "Driver": "local",
                "Mode": "z",
                "RW": true,
                "Propagation": ""
            }
        ],
        "Config": {
            "Hostname": "32b8ea353276",
            "Domainname": "",
            "User": "",
            "AttachStdin": false,
            "AttachStdout": true,
            "AttachStderr": true,
            "ExposedPorts": {
                "3306/tcp": {},
                "33060/tcp": {}
            },
            "Tty": false,
            "OpenStdin": false,
            "StdinOnce": false,
            "Env": [
                "MYSQL_ROOT_PASSWORD=keep",
                "MYSQL_DATABASE=keep",
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "GOSU_VERSION=1.16",
                "MYSQL_MAJOR=innovation",
                "MYSQL_VERSION=8.3.0-1.el8",
                "MYSQL_SHELL_VERSION=8.3.0-1.el8"
            ],
            "Cmd": [
                "mysqld"
            ],
            "Healthcheck": {
                "Test": [
                    "CMD-SHELL",
                    "mysqladmin ping -h localhost"
                ],
                "Interval": 10000000000,
                "Timeout": 5000000000,
                "Retries": 5
            },
            "Image": "mysql:latest",
            "Volumes": {
                "/var/lib/mysql": {}
            },
            "WorkingDir": "",
            "Entrypoint": [
                "docker-entrypoint.sh"
            ],
            "OnBuild": null,
            "Labels": {
                "com.docker.compose.config-hash": "59e50d7973326d9776ca757ea20fa9be64ab7d23af3eda0ef5024373e36b37a8",
                "com.docker.compose.container-number": "1",
                "com.docker.compose.depends_on": "",
                "com.docker.compose.image": "sha256:e68e2614955cad9955f5bf3eab032c5c5356e00ae1e7725e850cc0beec446214",
                "com.docker.compose.oneoff": "False",
                "com.docker.compose.project": "keep",
                "com.docker.compose.project.config_files": "/Users/shaharglazner/git/keep/tests/e2e_tests/docker-compose-e2e-mysql.yml",
                "com.docker.compose.project.working_dir": "/Users/shaharglazner/git/keep",
                "com.docker.compose.service": "keep-database",
                "com.docker.compose.version": "2.27.1"
            }
        },
        "NetworkSettings": {
            "Bridge": "",
            "SandboxID": "d026940f1bd64792f44381da8bc535f449fc1a6a82429e6ecc64ae2097a1b915",
            "SandboxKey": "/var/run/docker/netns/d026940f1bd6",
            "Ports": {
                "3306/tcp": [
                    {
                        "HostIp": "0.0.0.0",
                        "HostPort": "3306"
                    }
                ],
                "33060/tcp": null
            },
            "HairpinMode": false,
            "LinkLocalIPv6Address": "",
            "LinkLocalIPv6PrefixLen": 0,
            "SecondaryIPAddresses": null,
            "SecondaryIPv6Addresses": null,
            "EndpointID": "",
            "Gateway": "",
            "GlobalIPv6Address": "",
            "GlobalIPv6PrefixLen": 0,
            "IPAddress": "",
            "IPPrefixLen": 0,
            "IPv6Gateway": "",
            "MacAddress": "",
            "Networks": {
                "keep_default": {
                    "IPAMConfig": null,
                    "Links": null,
                    "Aliases": [
                        "keep-keep-database-1",
                        "keep-database"
                    ],
                    "MacAddress": "02:42:c0:a8:20:02",
                    "NetworkID": "6519b810e83623457ef3e39cde96d4058eb837b873cfdbadfb6282a7777678c8",
                    "EndpointID": "03b9688cc6f182099b438d39f0272b4928d1364db6f1014505c6a281d76ef298",
                    "Gateway": "192.168.32.1",
                    "IPAddress": "192.168.32.2",
                    "IPPrefixLen": 20,
                    "IPv6Gateway": "",
                    "GlobalIPv6Address": "",
                    "GlobalIPv6PrefixLen": 0,
                    "DriverOpts": null,
                    "DNSNames": [
                        "keep-keep-database-1",
                        "keep-database",
                        "32b8ea353276"
                    ]
                }
            }
        }
    }
]
