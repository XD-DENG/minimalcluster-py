from multiprocessing.managers import SyncManager
import multiprocessing
import sys
import getopt
import time
import datetime
from socket import getfqdn
if sys.version_info.major == 3:
    import queue as Queue
else:
    import Queue

__all__ = ['WorkerNode']

def single_worker(envir, fun, job_q, result_q, error_q):
    """ A worker function to be launched in a separate process. Takes jobs from
        job_q - each job a list of numbers to factorize. When the job is done,
        the result (dict mapping number -> list of factors) is placed into
        result_q. Runs until job_q is empty.
    """

    # Reference:
    #https://stackoverflow.com/questions/4484872/why-doesnt-exec-work-in-a-function-with-a-subfunction
    exec(envir) in locals()
    globals().update(locals())
    while True:
        try:
            job = job_q.get_nowait()
            outdict = {n: globals()[fun](n) for n in job}
            result_q.put(outdict)
        except Queue.Empty:
            return
        except:
            # send the Unexpected error to master node
            error_q.put("; ".join([repr(e) for e in sys.exc_info()]))
            return

def mp_apply(envir, fun, shared_job_q, shared_result_q, shared_error_q, nprocs):
    """ Split the work with jobs in shared_job_q and results in
        shared_result_q into several processes. Launch each process with
        single_worker as the worker function, and wait until all are
        finished.
    """
    
    procs = []
    for i in range(nprocs):
        p = multiprocessing.Process(
                target=single_worker,
                args=(envir, fun, shared_job_q, shared_result_q, shared_error_q))
        procs.append(p)
        p.start()

    for p in procs:
        p.join()

class WorkerNode():

    def __init__(self, IP, PORT, AUTHKEY, nprocs, quiet = False):
        '''
        Method to initiate a master node object.

        IP: the hostname or IP address of the Master Node
        PORT: the port to use (decided by Master NOde)
        AUTHKEY: The process's authentication key (a byte string).
                  It can't be None.
        nprocs: Integer. The number of processors on the Worker Node to be available to the Master Node.
                It should be less or equal to the number of processors on the Worker Node. If higher than that, the # of available processors will be used instead.
        '''

        assert AUTHKEY != None, "AUTHKEY can't be None"
        assert type(nprocs) == int, "'nprocs' must be an integer."

        self.IP = IP
        self.PORT = PORT
        self.AUTHKEY = AUTHKEY.encode()
        N_local_cores = multiprocessing.cpu_count()
        if nprocs > N_local_cores:
            print("[WARNING] nprocs specified is more than the # of cores of this node. Using the # of cores ({}) instead.".format(N_local_cores))
            self.nprocs = N_local_cores
        elif nprocs < 1:
            print("[WARNING] nprocs specified is not valid. Using the # of cores ({}) instead.".format(N_local_cores))
            self.nprocs = N_local_cores
        else:            
            self.nprocs = nprocs
        self.connected = False
        self.worker_hostname = getfqdn()
        self.quiet = quiet

    def connect(self):
        """
        Connect to Master Node after the Worker Node is initialized.
        """
        class ServerQueueManager(SyncManager):
            pass

        ServerQueueManager.register('get_job_q')
        ServerQueueManager.register('get_result_q')
        ServerQueueManager.register('get_error_q')
        ServerQueueManager.register('get_envir')
        ServerQueueManager.register('target_function')
        ServerQueueManager.register('queue_of_worker_list')

        self.manager = ServerQueueManager(address=(self.IP, self.PORT), authkey=self.AUTHKEY)
        
        try:
            if not self.quiet:
                print('[{}] Building connection to {}:{}'.format(str(datetime.datetime.now()), self.IP, self.PORT))
            self.manager.connect()
            if not self.quiet:
                print('[{}] Client connected to {}:{}'.format(str(datetime.datetime.now()), self.IP, self.PORT))
            self.connected = True
            self.job_q = self.manager.get_job_q()
            self.result_q = self.manager.get_result_q()
            self.error_q = self.manager.get_error_q()
            self.envir_to_use = self.manager.get_envir()
            self.target_func = self.manager.target_function()
            self.queue_of_worker_list = self.manager.queue_of_worker_list()
        except:
            print("[ERROR] No connection could be made. Please check the network or your configuration.")

    def join_cluster(self):
        """
        This method will connect the worker node with the master node, and start to listen to the master node for any job assignment.
        """

        self.connect()

        if self.connected:
            if not self.quiet:
                print('[{}] Listening to Master node {}:{}'.format(str(datetime.datetime.now()), self.IP, self.PORT))

            while True:

                # Check if the connection to master node is still working
                try:
                    if_job_q_empty = self.job_q.empty()

                    # to "notify" the master node this worker node is connected
                    if not self.queue_of_worker_list.empty():
                        self.queue_of_worker_list.put((self.worker_hostname, self.nprocs))

                except EOFError:
                    print("[{}] Lost connection with Master node.".format(str(datetime.datetime.now())))
                    sys.exit(1)

                if not if_job_q_empty and self.error_q.empty():
                    print("[{}] Started working on some tasks.".format(str(datetime.datetime.now())))


                    # load environment setup
                    try:
                        envir = self.envir_to_use.get(timeout = 3)
                        self.envir_to_use.put(envir)
                    except:
                        sys.exit("[ERROR] Failed to get the environment statement from Master node.")

                    # load task function
                    try:
                        target_func = self.target_func.get(timeout = 3)
                        self.target_func.put(target_func)
                    except:
                        sys.exit("[ERROR] Failed to get the task function from Master node.")
                    
                    mp_apply(envir, target_func, self.job_q, self.result_q, self.error_q, self.nprocs)
                    print("[{}] Tasked finished.".format(str(datetime.datetime.now())))

                time.sleep(0.1) # avoid too frequent communication which is unnecessary
