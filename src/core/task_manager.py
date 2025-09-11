"""Task Management System for Serena Project"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Task:
    """Individual task representation"""
    
    def __init__(
        self,
        task_id: str,
        name: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        status: TaskStatus = TaskStatus.PENDING,
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None
    ):
        self.task_id = task_id
        self.name = name
        self.description = description
        self.priority = priority
        self.status = status
        self.dependencies = dependencies or []
        self.metadata = metadata or {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.activated_at = None
        self.completed_at = None

    def activate(self):
        """Activate the task"""
        if self.status == TaskStatus.PENDING:
            self.status = TaskStatus.ACTIVE
            self.activated_at = datetime.now()
            self.updated_at = datetime.now()
            logger.info(f"Task '{self.name}' (ID: {self.task_id}) activated")
            return True
        else:
            logger.warning(f"Cannot activate task '{self.name}' - current status: {self.status.value}")
            return False

    def complete(self, result: Dict[str, Any] = None):
        """Complete the task"""
        if self.status == TaskStatus.ACTIVE:
            self.status = TaskStatus.COMPLETED
            self.completed_at = datetime.now()
            self.updated_at = datetime.now()
            if result:
                self.metadata.update({"result": result})
            logger.info(f"Task '{self.name}' (ID: {self.task_id}) completed")
            return True
        else:
            logger.warning(f"Cannot complete task '{self.name}' - current status: {self.status.value}")
            return False

    def fail(self, error: str = ""):
        """Mark task as failed"""
        self.status = TaskStatus.FAILED
        self.updated_at = datetime.now()
        if error:
            self.metadata["error"] = error
        logger.error(f"Task '{self.name}' (ID: {self.task_id}) failed: {error}")

    def cancel(self, reason: str = ""):
        """Cancel the task"""
        self.status = TaskStatus.CANCELLED
        self.updated_at = datetime.now()
        if reason:
            self.metadata["cancellation_reason"] = reason
        logger.info(f"Task '{self.name}' (ID: {self.task_id}) cancelled: {reason}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create task from dictionary"""
        task = cls(
            task_id=data["task_id"],
            name=data["name"],
            description=data["description"],
            priority=TaskPriority(data["priority"]),
            status=TaskStatus(data["status"]),
            dependencies=data["dependencies"],
            metadata=data["metadata"]
        )
        task.created_at = datetime.fromisoformat(data["created_at"])
        task.updated_at = datetime.fromisoformat(data["updated_at"])
        if data["activated_at"]:
            task.activated_at = datetime.fromisoformat(data["activated_at"])
        if data["completed_at"]:
            task.completed_at = datetime.fromisoformat(data["completed_at"])
        return task


class TaskManager:
    """Task management system"""
    
    def __init__(self, storage_path: str = ".serena/tasks.json"):
        self.storage_path = Path(storage_path)
        self.tasks: Dict[str, Task] = {}
        self.active_tasks: Dict[str, Task] = {}
        self.load_tasks()

    def load_tasks(self):
        """Load tasks from storage"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    for task_data in data.get("tasks", []):
                        task = Task.from_dict(task_data)
                        self.tasks[task.task_id] = task
                        if task.status == TaskStatus.ACTIVE:
                            self.active_tasks[task.task_id] = task
                logger.info(f"Loaded {len(self.tasks)} tasks from storage")
            except Exception as e:
                logger.error(f"Error loading tasks: {e}")

    def save_tasks(self):
        """Save tasks to storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "tasks": [task.to_dict() for task in self.tasks.values()],
                "saved_at": datetime.now().isoformat()
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.tasks)} tasks to storage")
        except Exception as e:
            logger.error(f"Error saving tasks: {e}")

    def create_task(
        self,
        name: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a new task"""
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.tasks)}"
        task = Task(
            task_id=task_id,
            name=name,
            description=description,
            priority=priority,
            dependencies=dependencies or [],
            metadata=metadata or {}
        )
        self.tasks[task_id] = task
        self.save_tasks()
        logger.info(f"Created task '{name}' (ID: {task_id})")
        return task_id

    def activate_task(self, task_id: str) -> bool:
        """Activate a specific task"""
        if task_id not in self.tasks:
            logger.error(f"Task ID '{task_id}' not found")
            return False
        
        task = self.tasks[task_id]
        
        # Check dependencies
        for dep_id in task.dependencies:
            if dep_id in self.tasks:
                dep_task = self.tasks[dep_id]
                if dep_task.status != TaskStatus.COMPLETED:
                    logger.warning(f"Cannot activate task '{task.name}' - dependency '{dep_task.name}' not completed")
                    return False
        
        if task.activate():
            self.active_tasks[task_id] = task
            self.save_tasks()
            return True
        return False

    def activate_tasks(self, task_ids: List[str] = None, filters: Dict[str, Any] = None) -> List[str]:
        """Activate multiple tasks"""
        activated = []
        
        if task_ids:
            # Activate specific tasks
            for task_id in task_ids:
                if self.activate_task(task_id):
                    activated.append(task_id)
        elif filters:
            # Activate tasks based on filters
            for task in self.tasks.values():
                if self._matches_filters(task, filters):
                    if self.activate_task(task.task_id):
                        activated.append(task.task_id)
        else:
            # Activate all pending tasks without dependencies
            for task in self.tasks.values():
                if task.status == TaskStatus.PENDING and not task.dependencies:
                    if self.activate_task(task.task_id):
                        activated.append(task.task_id)
        
        logger.info(f"Activated {len(activated)} tasks")
        return activated

    def complete_task(self, task_id: str, result: Dict[str, Any] = None) -> bool:
        """Complete a task"""
        if task_id not in self.tasks:
            logger.error(f"Task ID '{task_id}' not found")
            return False
        
        task = self.tasks[task_id]
        if task.complete(result):
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            self.save_tasks()
            return True
        return False

    def get_active_tasks(self) -> List[Task]:
        """Get all active tasks"""
        return list(self.active_tasks.values())

    def get_tasks(self, status: TaskStatus = None, priority: TaskPriority = None) -> List[Task]:
        """Get tasks with optional filtering"""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        if priority:
            tasks = [t for t in tasks if t.priority == priority]
        return tasks

    def get_task_stats(self) -> Dict[str, int]:
        """Get task statistics"""
        stats = {status.value: 0 for status in TaskStatus}
        for task in self.tasks.values():
            stats[task.status.value] += 1
        return stats

    def _matches_filters(self, task: Task, filters: Dict[str, Any]) -> bool:
        """Check if task matches filters"""
        for key, value in filters.items():
            if key == "status" and task.status.value != value:
                return False
            elif key == "priority" and task.priority.value != value:
                return False
            elif key == "name" and value.lower() not in task.name.lower():
                return False
        return True


# Global task manager instance
task_manager = TaskManager()