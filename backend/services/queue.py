"""
Async Processing Queue - Document upload and processing queue system
"""

import asyncio
from enum import Enum
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingTask:
    """A processing task"""
    
    def __init__(
        self,
        task_id: str,
        file_path: Path,
        client_id: str,
        task_type: str = "document_processing",
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.file_path = file_path
        self.client_id = client_id
        self.task_type = task_type
        self.metadata = metadata or {}
        self.status = ProcessingStatus.PENDING
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.progress: float = 0.0
        self.progress_message: Optional[str] = None


class ProcessingQueue:
    """Async processing queue for documents"""
    
    def __init__(self, max_workers: int = 3):
        """
        Initialize processing queue
        
        Args:
            max_workers: Maximum concurrent workers
        """
        self.max_workers = max_workers
        self.queue: asyncio.Queue = asyncio.Queue()
        self.tasks: Dict[str, ProcessingTask] = {}
        self.workers: List[asyncio.Task] = []
        self.is_running = False
        self.processor_func: Optional[Callable] = None
    
    def set_processor(self, processor_func: Callable) -> None:
        """Set the processor function"""
        self.processor_func = processor_func
    
    async def add_task(
        self,
        file_path: Path,
        client_id: str,
        task_type: str = "document_processing",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a task to the queue
        
        Args:
            file_path: Path to file to process
            client_id: Client ID
            task_type: Type of task
            metadata: Optional metadata
        
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        task = ProcessingTask(task_id, file_path, client_id, task_type, metadata)
        self.tasks[task_id] = task
        
        await self.queue.put(task)
        logger.info(f"Added task {task_id} to queue: {file_path}")
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[ProcessingTask]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    def get_tasks_by_status(self, status: ProcessingStatus) -> List[ProcessingTask]:
        """Get all tasks with a specific status"""
        return [task for task in self.tasks.values() if task.status == status]
    
    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine that processes tasks"""
        logger.info(f"Worker {worker_id} started")
        
        while self.is_running:
            try:
                # Get task from queue (with timeout)
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                
                # Update task status
                task.status = ProcessingStatus.PROCESSING
                task.started_at = datetime.utcnow()
                
                logger.info(f"Worker {worker_id} processing task {task.task_id}")
                
                # Process task
                try:
                    if self.processor_func:
                        result = await self.processor_func(task)
                        task.result = result
                        task.status = ProcessingStatus.COMPLETED
                        task.progress = 1.0
                        task.progress_message = "Completed"
                    else:
                        raise ValueError("No processor function set")
                
                except Exception as e:
                    logger.error(f"Error processing task {task.task_id}: {e}")
                    task.status = ProcessingStatus.FAILED
                    task.error = str(e)
                    task.progress_message = f"Error: {str(e)}"
                
                finally:
                    task.completed_at = datetime.utcnow()
                    self.queue.task_done()
                    logger.info(f"Worker {worker_id} completed task {task.task_id}")
            
            except asyncio.TimeoutError:
                # Timeout is expected when queue is empty
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)  # Wait before retrying
    
    async def start(self) -> None:
        """Start the queue workers"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Start workers
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self.workers.append(worker)
        
        logger.info(f"Processing queue started with {self.max_workers} workers")
    
    async def stop(self) -> None:
        """Stop the queue workers"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.cancel()
        
        # Wait for all workers to complete
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
        logger.info("Processing queue stopped")
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status == ProcessingStatus.PENDING:
            task.status = ProcessingStatus.CANCELLED
            return True
        
        return False
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self.queue.qsize()
    
    def get_active_tasks_count(self) -> int:
        """Get number of active (processing) tasks"""
        return len(self.get_tasks_by_status(ProcessingStatus.PROCESSING))


class ProcessingCache:
    """Cache for processing results"""
    
    def __init__(self, cache_dir: Path):
        """
        Initialize processing cache
        
        Args:
            cache_dir: Directory to store cache
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, file_path: Path) -> str:
        """Generate cache key from file path and modification time"""
        stat = file_path.stat()
        key_data = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, key_data))
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path"""
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Get cached result"""
        cache_key = self._get_cache_key(file_path)
        cache_path = self._get_cache_path(cache_key)
        
        if cache_path.exists():
            try:
                import json
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"Error loading cache: {e}")
                return None
        return None
    
    def set(self, file_path: Path, result: Dict[str, Any]) -> None:
        """Cache a result"""
        cache_key = self._get_cache_key(file_path)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            import json
            with open(cache_path, 'w') as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            logger.error(f"Error caching result: {e}")
    
    def clear(self) -> None:
        """Clear all cached results"""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Cleared processing cache")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
