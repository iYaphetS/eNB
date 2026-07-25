class ResourceRegistry:
    def __init__(self, close_fd=None):
        if close_fd is None:
            import os
            close_fd = os.close
        self._close_fd = close_fd
        self._resources = []

    def add(self, resource):
        self._resources.append(('resource', resource))
        return resource

    def add_fd(self, file_descriptor):
        self._resources.append(('fd', file_descriptor))
        return file_descriptor

    def close(self):
        while self._resources:
            resource_type, resource = self._resources.pop()
            try:
                if resource_type == 'fd':
                    self._close_fd(resource)
                else:
                    resource.close()
            except OSError:
                pass
