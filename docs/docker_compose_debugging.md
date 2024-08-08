# Docker compose debugging

## Installing Docker

One way to install Docker along with all the necessary tools (such as docker-compose) is to install [Docker Desktop](https://www.docker.com/products/docker-desktop/). This will also give you a user interface that will prove helpful for debugging, especially if you are not experienced with Docker.

## Resource requirements

You must ensure that Docker has sufficient resources to run Codex. The default resource allocations are probably not sufficient - you can update the them in Docker Desktop under Settings -> Resources. The following minimum resource allocations are known to work:

CPUs - 8
Memory - 16GB
Swap - 4GB
Disk image size - 60GB

Note that on Windows resource allocations cannot be set from the Docker Desktop UI, please see the Windows section below for more details.

## Elasticsearch container crashing

There is a known issue that might be causing your ES container to crash.

## Windows

The best way to run docker-compose on Windows is using WSL2. Use the [official documentation](https://docs.microsoft.com/en-us/windows/wsl/install) to install WSL2 and one of the Linux distributions. The latest stable release of Ubuntu is known to work.

Tip: clone houston and codex-frontend (if using) into a folder on the Linux subsystem. While it may seem like you can interact with files and folders outside of the subsystem normally, issues will arise when Docker attempts to use them.

When using WSL2, resource allocations are set for the Linux subsystem and inherited by Docker. These can be set using a `.wslconfig` file stored in the home directory. The following file contents will work, but you can also browse [Microsoft's wslconfig documentation](https://docs.microsoft.com/en-us/windows/wsl/wsl-config) for more configuration options.

```
[wsl2]
memory=16gb
swap=4gb
localhostforwarding=true
localhostForwarding=true
```
