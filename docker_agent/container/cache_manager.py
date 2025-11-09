"""Container and image cache manager"""

import docker
import os
import logging
from pathlib import Path
from typing import Dict, Optional, Any

from docker_agent.core.types import Container
from docker_agent.container.image_builder import DockerImageBuilder
from docker_agent.config.config import DOCKER_ENVIRONMENT
from docker_agent.core.exceptions import CacheError


class CacheManager:
    """Container and image cache manager"""

    def __init__(self, repo: str, repo_id: str, timeout=300):
        self.base_path = Path(__file__).parent.parent
        self.logger = logging.getLogger(__name__)
        self.client = docker.from_env(timeout=timeout)
        self.repo = repo.replace("/", "_")
        self.repo_id = repo_id
        self.repo_lower = self.repo.lower()
        self.image_builder = DockerImageBuilder(self.base_path, timeout)

    @property
    def common_container_config(self) -> Dict[str, Any]:
        """Extract and return common container creation parameters"""

        config = {
            "name": self.repo,
            "command": "/bin/bash",
            "detach": True,
            "tty": True,
            "runtime": "nvidia",
            "network_mode": "host",
            "device_requests": [{
                'count': -1,
                'capabilities': [['gpu']]
            }],
            "environment": DOCKER_ENVIRONMENT,
            "volumes": {
                str(self.base_path / "swap"): {
                    "bind": "/workdir/swap",
                    "mode": "rw"
                }
            }
        }

        if os.name == 'posix':
            uid = os.getuid()
            gid = os.getgid()
            self.logger.info(f"Running on POSIX system, setting container user to UID={uid}, GID={gid}")
            config['user'] = f"{uid}:{gid}"

        return config

    def check_cached_container(self) -> Optional[Container]:
        """Check if cached container exists"""

        try:
            # Find existing containers
            container = self.client.containers.get(self.repo)

            # Check container status
            if container.status == 'running':
                self.logger.info(f"Found running cached container: {self.repo}")
                return container
            elif container.status == 'exited':
                self.logger.info(f"Found stopped cached container: {self.repo}, restarting...")
                container.start()
                return container
            else:
                self.logger.warning(f"Container {self.repo} status abnormal: {container.status}, will recreate")
                container.remove(force=True)
                return None

        except docker.errors.NotFound:
            self.logger.info(f"Cached container not found: {self.repo}")
            return None
        except Exception as e:
            self.logger.error(f"Error checking cached container: {str(e)}")
            return None

    def save_container_as_image(self, container: Container) -> str:
        """Save container as new image"""

        # Image name must be lowercase
        image_name = f"featbench_{self.repo_lower}"

        try:
            self.logger.info(f"Saving container as image: {image_name}")

            # Commit container as new image
            image = container.commit(repository=image_name, tag=self.repo_id)

            self.logger.info(f"Successfully saved image: {image_name}:latest (ID: {image.id[:12]})")
            return image.id

        except Exception as e:
            self.logger.error(f"Failed to save container image: {str(e)}")
            raise CacheError(f"Failed to save container image: {str(e)}")

    def check_cached_image(self) -> bool:
        """Check if cached image exists"""

        image_name = f"featbench_{self.repo_lower}:{self.repo_id}"

        try:
            self.client.images.get(image_name)
            self.logger.info(f"Found cached image: {image_name}")
            return True
        except docker.errors.ImageNotFound:
            self.logger.info(f"Cached image not found: {image_name}")
            return False
        except Exception as e:
            self.logger.error(f"Error checking cached image: {str(e)}")
            return False

    def create_container_from_cached_image(self) -> Container:
        """Create container from cached image"""

        image_name = f"featbench_{self.repo_lower}:{self.repo_id}"

        self.logger.info(f"Creating container from cached image: {image_name}")

        container = self.client.containers.run(
            image=image_name,
            **self.common_container_config
        )

        self.logger.info(f"Successfully created container from cached image: {self.repo}")
        return container

    def create_new_container(self) -> Container:
        """Create new container"""
        self.logger.info(f"Creating new container: {self.repo}")

        # Build dynamic image
        image_name = self.image_builder.build_image(self.repo)

        # Create container with GPU support
        container = self.client.containers.run(
            image=image_name,
            **self.common_container_config
        )

        self.logger.info(f"Container {self.repo} created successfully")
        return container