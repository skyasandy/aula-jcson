# taskmanager/models/task.py
"""
Módulo de modelos de domínio para tarefas.

Este módulo define as entidades fundamentais do sistema de gerenciamento
de tarefas, implementando validações robustas e type safety através
do Pydantic v2.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator, ConfigDict


class TaskPriority(str, Enum):
    """
    Enumeração para prioridades de tarefa.
    
    Herda de str para serialização automática e compatibilidade
    com sistemas externos que esperam strings.
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """
    Estados possíveis de uma tarefa no sistema.
    
    Implementa máquina de estados simples:
    PENDING -> IN_PROGRESS -> COMPLETED
    PENDING -> CANCELLED
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """
    Modelo de domínio para uma tarefa.
    
    Representa uma tarefa no sistema com todas as informações
    necessárias para gerenciamento completo, incluindo metadados
    de auditoria e validações de negócio.
    
    Atributos:
        id: Identificador único da tarefa
        title: Título descritivo da tarefa (obrigatório)
        description: Descrição detalhada (opcional)
        priority: Prioridade da tarefa (padrão: MEDIUM)
        status: Status atual da tarefa (padrão: PENDING)
        created_at: Timestamp de criação (UTC)
        updated_at: Timestamp da última atualização (UTC)
        due_date: Data limite para conclusão (opcional)
        assigned_to: ID do usuário responsável (opcional)
        tags: Lista de tags para categorização
        estimated_hours: Estimativa de esforço em horas
        
    Exemplo:
        >>> task = Task(
        ...     title="Implementar autenticação",
        ...     description="Adicionar JWT auth ao sistema",
        ...     priority=TaskPriority.HIGH,
        ...     estimated_hours=8.0
        ... )
        >>> print(task.title)
        Implementar autenticação
    """
    
    # Configuração do Pydantic v2
    model_config = ConfigDict(
        # Permite validação de assignment após criação
        validate_assignment=True,
        # Usa enums por valor ao serializar
        use_enum_values=True,
        # Permite campos extras (flexibilidade futura)
        extra='allow',
        # Validação rigorosa de tipos
        strict=True
    )
    
    # Campos obrigatórios
    id: UUID = Field(
        default_factory=uuid4,
        description="Identificador único da tarefa"
    )
    
    title: str = Field(
        min_length=1,
        max_length=200,
        description="Título da tarefa"
    )
    
    # Campos com valores padrão
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM,
        description="Prioridade da tarefa"
    )
    
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Status atual da tarefa"
    )
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp de criação em UTC"
    )
    
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp da última atualização em UTC"
    )
    
    # Campos opcionais
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Descrição detalhada da tarefa"
    )
    
    due_date: Optional[datetime] = Field(
        default=None,
        description="Data limite para conclusão"
    )
    
    assigned_to: Optional[UUID] = Field(
        default=None,
        description="ID do usuário responsável"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Tags para categorização"
    )
    
    estimated_hours: Optional[float] = Field(
        default=None,
        ge=0.0,  # Maior ou igual a zero
        le=1000.0,  # Limite razoável
        description="Estimativa de esforço em horas"
    )
    
    @validator('due_date')
    @classmethod
    def validate_due_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        """
        Valida que a data limite não seja no passado.
        
        Regra de negócio: Não permitir criação de tarefas
        com prazo vencido, exceto em casos específicos de
        migração de dados.
        
        Args:
            v: Data limite a ser validada
            
        Returns:
            Data validada ou None
            
        Raises:
            ValueError: Se a data for anterior ao momento atual
        """
        if v is not None and v < datetime.now(timezone.utc):
            raise ValueError(
                "Data limite não pode ser anterior ao momento atual"
            )
        return v
    
    @validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """
        Normaliza e valida tags.
        
        Aplica transformações de higienização:
        - Remove espaços em branco extras
        - Converte para lowercase
        - Remove duplicatas
        - Limita a 10 tags por tarefa
        
        Args:
            v: Lista de tags
            
        Returns:
            Lista de tags normalizada
            
        Raises:
            ValueError: Se houver mais de 10 tags
        """
        # Normalização: trim, lowercase, deduplicação
        normalized_tags = list(set(
            tag.strip().lower() 
            for tag in v 
            if tag.strip()  # Remove tags vazias
        ))
        
        # Validação de limite
        if len(normalized_tags) > 10:
            raise ValueError("Máximo de 10 tags permitidas por tarefa")
        
        return normalized_tags
    
    def mark_in_progress(self) -> None:
        """
        Transiciona tarefa para status 'in_progress'.
        
        Implementa validação de transição de estado:
        Só permite transição de PENDING para IN_PROGRESS.
        
        Raises:
            ValueError: Se a transição não for válida
        """
        if self.status != TaskStatus.PENDING:
            raise ValueError(
                f"Não é possível marcar como 'in_progress' "
                f"tarefa com status '{self.status}'"
            )
        
        self.status = TaskStatus.IN_PROGRESS
        self.updated_at = datetime.now(timezone.utc)
    
    def mark_completed(self) -> None:
        """
        Marca tarefa como concluída.
        
        Permite transição de PENDING ou IN_PROGRESS para COMPLETED.
        Atualiza automaticamente o timestamp de atualização.
        
        Raises:
            ValueError: Se a tarefa já estiver concluída ou cancelada
        """
        if self.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise ValueError(
                f"Tarefa já está finalizada com status '{self.status}'"
            )
        
        self.status = TaskStatus.COMPLETED
        self.updated_at = datetime.now(timezone.utc)
    
    def cancel(self, reason: Optional[str] = None) -> None:
        """
        Cancela uma tarefa.
        
        Args:
            reason: Motivo do cancelamento (opcional)
        """
        if self.status == TaskStatus.COMPLETED:
            raise ValueError("Não é possível cancelar tarefa já concluída")
        
        self.status = TaskStatus.CANCELLED
        self.updated_at = datetime.now(timezone.utc)
        
        # Adiciona razão às tags se fornecida
        if reason:
            self.tags.append(f"cancelled:{reason}")
    
    @property
    def is_overdue(self) -> bool:
        """
        Verifica se a tarefa está atrasada.
        
        Returns:
            True se a data limite passou e a tarefa não está concluída
        """
        if self.due_date is None:
            return False
        
        return (
            self.due_date < datetime.now(timezone.utc) 
            and self.status != TaskStatus.COMPLETED
        )
    
    @property
    def age_in_days(self) -> int:
        """
        Calcula a idade da tarefa em dias.
        
        Returns:
            Número de dias desde a criação
        """
        delta = datetime.now(timezone.utc) - self.created_at
        return delta.days
    
    def to_dict(self) -> dict:
        """
        Converte para dicionário para serialização.
        
        Returns:
            Representação em dicionário do objeto
        """
        return self.model_dump(mode='json')
    
    def __str__(self) -> str:
        """Representação string amigável."""
        return f"Task('{self.title}', {self.status}, {self.priority})"
    
    def __repr__(self) -> str:
        """Representação técnica para debugging."""
        return (
            f"Task(id={self.id}, title='{self.title}', "
            f"status={self.status}, priority={self.priority})"
        )


# Factory functions para casos comuns
def create_urgent_task(title: str, description: str, due_hours: int = 24) -> Task:
    """
    Factory para criar tarefas urgentes.
    
    Conveniência para criação de tarefas críticas com prazo
    pré-definido e prioridade alta.
    
    Args:
        title: Título da tarefa
        description: Descrição detalhada
        due_hours: Horas até o prazo (padrão: 24h)
        
    Returns:
        Tarefa configurada como crítica
    """
    due_date = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(hours=due_hours)
    
    return Task(
        title=title,
        description=description,
        priority=TaskPriority.CRITICAL,
        due_date=due_date,
        tags=["urgent", "high-priority"]
    )


def create_routine_task(title: str, tags: Optional[List[str]] = None) -> Task:
    """
    Factory para tarefas de rotina.
    
    Args:
        title: Título da tarefa
        tags: Tags adicionais (padrão: ["routine"])
        
    Returns:
        Tarefa configurada para rotina
    """
    default_tags = tags or []
    default_tags.append("routine")
    
    return Task(
        title=title,
        priority=TaskPriority.LOW,
        tags=default_tags,
        estimated_hours=1.0
    )