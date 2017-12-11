
__all__ = ['MasterNode', "WorkerNode"]


import sys
if sys.version_info.major == 3:
    from .master_node import MasterNode
    from .worker_node import WorkerNode
else:
    from master_node import MasterNode
    from worker_node import WorkerNode
