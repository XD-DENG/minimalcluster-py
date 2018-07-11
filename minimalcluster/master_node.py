from multiprocessing.managers import SyncManager, DictProxy
from multiprocessing import Process, cpu_count
import os, signal, sys, time, datetime, random, string, inspect
from functools import partial
from types import FunctionType
from socket import getfqdn
if sys.version_info.major == 3:
    from queue import Queue as _Queue
else:
    from Queue import Queue as _Queue



__all__ = ['MasterNode']
    


# Make Queue.Queue pickleable
# Ref: https://stackoverflow.com/questions/25631266/cant-pickle-class-main-jobqueuemanager
class Queue(_Queue):
    """ A picklable queue. """   
    def __getstate__(self):
        # Only pickle the state we care about
        return (self.maxsize, self.queue, self.unfinished_tasks)

    def __setstate__(self, state):
        # Re-initialize the object, then overwrite the default state with
        # our pickled state.
        Queue.__init__(self)
        self.maxsize = state[0]
        self.queue = state[1]
        self.unfinished_tasks = state[2]

# prepare for using functools.partial()
def get_fun(fun):
    return fun



class JobQueueManager(SyncManager):
    pass


def clear_queue(q):
    while not q.empty():
        q.get()


def start_worker_in_background(HOST, PORT, AUTHKEY, nprocs, quiet):
    from minimalcluster import WorkerNode
    worker = WorkerNode(HOST, PORT, AUTHKEY, nprocs, quiet)
    worker.join_cluster()


class MasterNode():

    def __init__(self, HOST = '127.0.0.1', PORT = 8888, AUTHKEY = None, chunksize = 50):
        '''
        Method to initiate a master node object.

        HOST: the hostname or IP address to use
        PORT: the port to use
        AUTHKEY: The process's authentication key (a string or byte string).
                 If None is given, a random string will be given
        chunksize: The numbers are split into chunks. Each chunk is pushed into the job queue.
                   Here the size of each chunk if specified.
        '''

        # Check & process AUTHKEY
        # to [1] ensure compatilibity between Py 2 and 3; [2] to allow both string and byte string for AUTHKEY input.
        assert type(AUTHKEY) in [str, bytes] or AUTHKEY is None, "AUTKEY must be either one among string, byte string, and None (a random AUTHKEY will be generated if None is given)."
        if AUTHKEY != None and type(AUTHKEY) == str:
            AUTHKEY = AUTHKEY.encode()

        self.HOST = HOST
        self.PORT = PORT
        self.AUTHKEY = AUTHKEY if AUTHKEY != None else ''.join(random.choice(string.ascii_uppercase) for _ in range(6)).encode()
        self.chunksize = chunksize
        self.server_status = 'off'
        self.as_worker = False
        self.target_fun = None
        self.master_fqdn = getfqdn()
        self.pid_as_worker_on_master = None


    def join_as_worker(self):
        '''
        This method helps start the master node as a worker node as well
        '''
        if self.as_worker:
            print("[WARNING] This node has already joined the cluster as a worker node.")
        else:
            self.process_as_worker = Process(target = start_worker_in_background, args=(self.HOST, self.PORT, self.AUTHKEY, cpu_count(), True, ))
            self.process_as_worker.start()
            
            # waiting for the master node joining the cluster as a worker
            while self.master_fqdn not in [w[0] for w in self.list_workers()]:
                pass

            self.pid_as_worker_on_master = [w for w in self.list_workers() if w[0] == self.master_fqdn][0][2]
            self.as_worker = True
            print("[INFO] Current node has joined the cluster as a Worker Node (using {} processors; Process ID: {}).".format(cpu_count(), self.process_as_worker.pid))
        
    def start_master_server(self, if_join_as_worker = True):
        """
        Method to create a manager as the master node.
        
        Arguments:
        if_join_as_worker: Boolen.
                        If True, the master node will also join the cluster as worker node. It will automatically run in background.
                        If False, users need to explicitly configure if they want the master node to work as worker node too.
                        The default value is True.                             
        """
        self.job_q = Queue()
        self.result_q = Queue()
        self.error_q = Queue()
        self.get_envir = Queue()
        self.target_function = Queue()
        self.raw_queue_of_worker_list = Queue()
        self.raw_dict_of_job_history = dict() # a queue to store the history of job assignment
        
        # Return synchronized proxies for the actual Queue objects.
        # Note that for "callable=", we don't use `lambda` which is commonly used in multiprocessing examples.
        # Instead, we use `partial()` to wrapper one more time.
        # This is to avoid "pickle.PicklingError" on Windows platform. This helps the codes run on both Windows and Linux/Mac OS.
        # Ref: https://stackoverflow.com/questions/25631266/cant-pickle-class-main-jobqueuemanager

        JobQueueManager.register('get_job_q', callable=partial(get_fun, self.job_q))
        JobQueueManager.register('get_result_q', callable=partial(get_fun, self.result_q))
        JobQueueManager.register('get_error_q', callable=partial(get_fun, self.error_q))
        JobQueueManager.register('get_envir', callable = partial(get_fun, self.get_envir))
        JobQueueManager.register('target_function', callable = partial(get_fun, self.target_function))
        JobQueueManager.register('queue_of_worker_list', callable = partial(get_fun, self.raw_queue_of_worker_list))
        JobQueueManager.register('dict_of_job_history', callable = partial(get_fun, self.raw_dict_of_job_history), proxytype=DictProxy)

        self.manager = JobQueueManager(address=(self.HOST, self.PORT), authkey=self.AUTHKEY)
        self.manager.start()
        self.server_status = 'on'
        print('[{}] Master Node started at {}:{} with authkey `{}`.'.format(str(datetime.datetime.now()), self.HOST, self.PORT, self.AUTHKEY.decode()))

        self.shared_job_q = self.manager.get_job_q()
        self.shared_result_q = self.manager.get_result_q()
        self.shared_error_q = self.manager.get_error_q()
        self.share_envir = self.manager.get_envir()
        self.share_target_fun = self.manager.target_function()
        self.queue_of_worker_list = self.manager.queue_of_worker_list()
        self.dict_of_job_history = self.manager.dict_of_job_history()
        
        if if_join_as_worker:
            self.join_as_worker()

    def stop_as_worker(self):
        '''
        Given the master node can also join the cluster as a worker, we also need to have a method to stop it as a worker node (which may be necessary in some cases).
        This method serves this purpose.

        Given the worker node will start a separate process for heartbeat purpose.
        We need to shutdown the heartbeat process separately.
        '''
        try:
            os.kill(self.pid_as_worker_on_master, signal.SIGTERM)
            self.pid_as_worker_on_master = None
            self.process_as_worker.terminate()
        except AttributeError:
            print("[WARNING] The master node has not started as a worker yet.")
        finally:
            self.as_worker = False
            print("[INFO] The master node has stopped working as a worker node.")

    def list_workers(self):
        '''
        Return a list of connected worker nodes.
        Each element of this list is:
            (hostname of worker node,
             # of available cores,
             pid of heartbeat process on the worker node,
             if the worker node is working on any work load currently (1:Yes, 0:No))
        '''

        # STEP-1: an element will be PUT into the queue "self.queue_of_worker_list"
        # STEP-2: worker nodes will watch on this queue and attach their information into this queue too
        # STEP-3: this function will collect the elements from the queue and return the list of workers node who responded

        self.queue_of_worker_list.put(".") # trigger worker nodes to contact master node to show their "heartbeat"
        time.sleep(0.3) # Allow some time for collecting "heartbeat"
        
        worker_list = []
        while not self.queue_of_worker_list.empty():
            worker_list.append(self.queue_of_worker_list.get())

        return list(set([w for w in worker_list if w != "."]))
        

    def load_envir(self, source, from_file = True):
        if from_file:
            with open(source, 'r') as f:
                self.envir_statements = "".join(f.readlines())
        else:
            self.envir_statements = source   
        
    def register_target_function(self, fun_name):
        self.target_fun = fun_name
        
    def load_args(self, args):
        '''
        args should be a list
        '''
        self.args_to_share_to_workers = args


    def __check_target_function(self):

        try:
            exec(self.envir_statements)
        except:
            print("[ERROR] The environment statements given can't be executed.")
            raise

        if self.target_fun in locals() and isinstance(locals()[self.target_fun], FunctionType):
            return True
        else:
            return False


    def execute(self):

        # Ensure the error queue is empty
        clear_queue(self.shared_error_q)

        if self.target_fun == None:
            print("[ERROR] Target function is not registered yet.")
        elif not self.__check_target_function():
            print("[ERROR] The target function registered (`{}`) can't be built with the given environment statements.".format(self.target_fun))
        elif len(self.args_to_share_to_workers) != len(set(self.args_to_share_to_workers)):
            print("[ERROR]The arguments to share with worker nodes are not unique. Please check the data you passed to MasterNode.load_args().")
        elif len(self.list_workers()) == 0:
            print("[ERROR] No worker node is available. Can't proceed to execute")
        else:
            print("[{}] Assigning jobs to worker nodes.".format(str(datetime.datetime.now())))

            
            self.share_envir.put(self.envir_statements)

            self.share_target_fun.put(self.target_fun)

            # The numbers are split into chunks. Each chunk is pushed into the job queue
            for i in range(0, len(self.args_to_share_to_workers), self.chunksize):
                self.shared_job_q.put((i, self.args_to_share_to_workers[i:(i + self.chunksize)]))
            
            # Wait until all results are ready in shared_result_q
            numresults = 0
            resultdict = {}
            list_job_id_done = []
            while numresults < len(self.args_to_share_to_workers):

                if len(self.list_workers()) == 0:
                    print("[{}][Warning] No valid worker node at this moment. You can wait for workers to join, or CTRL+C to cancle.".format(str(datetime.datetime.now())))
                    continue

                if self.shared_job_q.empty() and sum([w[3] for w in self.list_workers()]) == 0:
                    '''
                    After all jobs are assigned and all worker nodes have finished their works,
                    check if the nodes who have un-finished jobs are sitll alive.
                    if not, re-collect these jobs and put them inot the job queue
                    '''
                    while not self.shared_result_q.empty():
                        try:
                            job_id_done, outdict = self.shared_result_q.get(False)
                            resultdict.update(outdict)
                            list_job_id_done.append(job_id_done)
                            numresults += len(outdict)
                        except:
                            pass

                    [self.dict_of_job_history.pop(k, None) for k in list_job_id_done]

                    for job_id in [x for x,y in self.dict_of_job_history.items()]:
                        print("Putting {} back to the job queue".format(job_id))
                        self.shared_job_q.put((job_id, self.args_to_share_to_workers[job_id:(job_id + self.chunksize)]))

                if not self.shared_error_q.empty():
                    print("[ERROR] Running error occured in remote worker node:")
                    print(self.shared_error_q.get())
                    
                    clear_queue(self.shared_job_q)
                    clear_queue(self.shared_result_q)
                    clear_queue(self.share_envir)
                    clear_queue(self.share_target_fun)
                    clear_queue(self.shared_error_q)
                    self.dict_of_job_history.clear()

                    return None

                # job_id_done is the unique id of the jobs that have been done and returned to the master node.
                while not self.shared_result_q.empty():
                    try:
                        job_id_done, outdict = self.shared_result_q.get(False)
                        resultdict.update(outdict)
                        list_job_id_done.append(job_id_done)
                        numresults += len(outdict)
                    except:
                        pass


            print("[{}] Aggregating on Master node...".format(str(datetime.datetime.now())))

            # After the execution is done, empty all the args & task function queues
            # to prepare for the next execution
            clear_queue(self.shared_job_q)
            clear_queue(self.shared_result_q)
            clear_queue(self.share_envir)
            clear_queue(self.share_target_fun)
            self.dict_of_job_history.clear()

            return resultdict


    def shutdown(self):
        if self.as_worker:
            self.stop_as_worker()

        if self.server_status == 'on':
            self.manager.shutdown()
            self.server_status = "off"
            print("[INFO] The master node is shut down.")
        else:
            print("[WARNING] The master node is not started yet or already shut down.")
