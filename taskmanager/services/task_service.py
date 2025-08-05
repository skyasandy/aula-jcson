# taskmanager/services/task_service.py
"""
Serviço de negócio para gerenciamento de tarefas.

Este módulo implementa a lógica de negócio para operações
com tarefas, abstraindo a persistência e fornecendo
interface limpa para a camada de apresentação.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from ..models.task import Task, TaskStatus, TaskPriority
from ..core.exceptions import TaskNotFoundError, BusinessRuleError


class TaskService:
    """
    Serviço de gerenciamento de tarefas.
    
    Implementa padrão Repository abstraindo persistência
    e concentrando regras de negócio em um local central.
    
    Responsabilidades:
    - Validação de regras de negócio
    - Orquestração de operações complexas
    - Manutenção de invariantes do domínio
    - Interface limpa para controllers
    """
    
    def __init__(self) -> None:
        """
        Inicializa o serviço com repositório em memória.
        
        NOTA: Em aplicação real, injetaríamos uma implementação
        de repositório (database, file system, etc.)
        """
        # Simulação de repositório em memória
        # Em aplicação real: self._repository = task_repository
        self._tasks: Dict[UUID, Task] = {}
        
        # Métricas simples para demonstração
        self._stats = {
            "total_created": 0,
            "total_completed": 0,
            "total_cancelled": 0,
        }
    
    def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[datetime] = None,
        assigned_to: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        estimated_hours: Optional[float] = None,
    ) -> Task:
        """
        Cria uma nova tarefa aplicando regras de negócio.
        
        Regras aplicadas:
        - Título é obrigatório e não pode ser vazio
        - Data limite não pode ser no passado
        - Tarefas críticas requerem data limite
        - Estimativa deve ser realística (< 40h por tarefa)
        
        Args:
            title: Título da tarefa
            description: Descrição opcional
            priority: Prioridade (padrão: MEDIUM)
            due_date: Data limite opcional
            assigned_to: ID do responsável opcional
            tags: Lista de tags opcional
            estimated_hours: Estimativa de esforço opcional
            
        Returns:
            Nova tarefa criada
            
        Raises:
            BusinessRuleError: Se regras de negócio forem violadas
        """
        # Validação de regra de negócio: tarefas críticas precisam de prazo
        if priority == TaskPriority.CRITICAL and due_date is None:
            raise BusinessRuleError(
                "Tarefas críticas devem ter data limite definida"
            )
        
        # Validação de estimativa realística
        if estimated_hours is not None and estimated_hours > 40.0:
            raise BusinessRuleError(
                "Estimativa não pode exceder 40 horas por tarefa. "
                "Considere dividir em tarefas menores."
            )
        
        # Criação da tarefa
        task = Task(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            assigned_to=assigned_to,
            tags=tags or [],
            estimated_hours=estimated_hours,
        )
        
        # Persistência (simulada)
        self._tasks[task.id] = task
        self._stats["total_created"] += 1
        
        return task
    
    def get_task(self, task_id: UUID) -> Task:
        """
        Recupera tarefa por ID.
        
        Args:
            task_id: Identificador da tarefa
            
        Returns:
            Tarefa encontrada
            
        Raises:
            TaskNotFoundError: Se tarefa não existir
        """
        task = self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"Tarefa {task_id} não encontrada")
        
        return task
    
    def update_task(
        self,
        task_id: UUID,
        **updates: Any
    ) -> Task:
        """
        Atualiza tarefa aplicando validações.
        
        Args:
            task_id: ID da tarefa
            **updates: Campos a serem atualizados
            
        Returns:
            Tarefa atualizada
            
        Raises:
            TaskNotFoundError: Se tarefa não existir
            BusinessRuleError: Se atualização violar regras
        """
        task = self.get_task(task_id)
        
        # Aplicar atualizações validando regras de negócio
        for field, value in updates.items():
            if field == "status":
                self._validate_status_transition(task, value)
            
            setattr(task, field, value)
        
        # Atualizar timestamp
        task.updated_at = datetime.now(timezone.utc)
        
        return task
    
    def complete_task(self, task_id: UUID) -> Task:
        """
        Marca tarefa como concluída.
        
        Implementa lógica específica de conclusão:
        - Valida transição de estado
        - Atualiza métricas
        - Registra timestamp de conclusão
        
        Args:
            task_id: ID da tarefa
            
        Returns:
            Tarefa concluída
        """
        task = self.get_task(task_id)
        task.mark_completed()
        
        # Atualizar métricas
        self._stats["total_completed"] += 1
        
        return task
    
    def cancel_task(self, task_id: UUID, reason: Optional[str] = None) -> Task:
        """
        Cancela uma tarefa.
        
        Args:
            task_id: ID da tarefa
            reason: Motivo do cancelamento
            
        Returns:
            Tarefa cancelada
        """
        task = self.get_task(task_id)
        task.cancel(reason)
        
        # Atualizar métricas
        self._stats["total_cancelled"] += 1
        
        return task
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        assigned_to: Optional[UUID] = None,
        tag: Optional[str] = None,
        overdue_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Task]:
        """
        Lista tarefas com filtros opcionais.
        
        Args:
            status: Filtrar por status
            priority: Filtrar por prioridade
            assigned_to: Filtrar por responsável
            tag: Filtrar por tag específica
            overdue_only: Apenas tarefas atrasadas
            limit: Número máximo de resultados
            offset: Número de registros a pular
            
        Returns:
            Lista de tarefas filtradas
        """
        tasks = list(self._tasks.values())
        
        # Aplicar filtros
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        
        if priority is not None:
            tasks = [t for t in tasks if t.priority == priority]
        
        if assigned_to is not None:
            tasks = [t for t in tasks if t.assigned_to == assigned_to]
        
        if tag is not None:
            tasks = [t for t in tasks if tag in t.tags]
        
        if overdue_only:
            tasks = [t for t in tasks if t.is_overdue]
        
        # Ordenar por data de criação (mais recentes primeiro)
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        # Aplicar paginação
        return tasks[offset:offset + limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatísticas do sistema.
        
        Returns:
            Dicionário com métricas agregadas
        """
        total_tasks = len(self._tasks)
        active_tasks = len([
            t for t in self._tasks.values()
            if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
        ])
        overdue_tasks = len([
            t for t in self._tasks.values()
            if t.is_overdue
        ])
        
        return {
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "overdue_tasks": overdue_tasks,
            "completion_rate": (
                self._stats["total_completed"] / max(1, total_tasks) * 100
            ),
            **self._stats,
        }
    
    def _validate_status_transition(
        self, 
        task: Task, 
        new_status: TaskStatus
    ) -> None:
        """
        Valida transições de status permitidas.
        
        Implementa máquina de estados:
        PENDING -> IN_PROGRESS, COMPLETED, CANCELLED
        IN_PROGRESS -> COMPLETED, CANCELLED
        COMPLETED -> (sem transições)
        CANCELLED -> (sem transições)
        
        Args:
            task: Tarefa atual
            new_status: Novo status desejado
            
        Raises:
            BusinessRuleError: Se transição não for permitida
        """
        current = task.status
        
        # Transições inválidas
        if current in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise BusinessRuleError(
                f"Não é possível alterar status de tarefa {current}"
            )
        
        # Validação específica: IN_PROGRESS não pode voltar para PENDING
        if current == TaskStatus.IN_PROGRESS and new_status == TaskStatus.PENDING:
            raise BusinessRuleError(
                "Tarefa em progresso não pode voltar para pendente"
            )