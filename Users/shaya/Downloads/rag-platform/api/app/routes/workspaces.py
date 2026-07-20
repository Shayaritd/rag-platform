import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project, Tenant, User
from app.schemas.workspace import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate
from app.core.security import CurrentUser, get_current_user

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> list[Tenant]:
    return db.query(Tenant).filter(Tenant.id == user.tenant_id).all()


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Tenant:
    tenant = Tenant(name=payload.name or "New workspace", plan=payload.plan or "free")
    db.add(tenant)
    db.flush()

    user_record = db.query(User).filter(User.id == user.user_id).first()
    if user_record:
        user_record.tenant_id = tenant.id

    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/{id}", response_model=WorkspaceOut)
def get_workspace(id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> Tenant:
    tenant_id = uuid.UUID(id)
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id, Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return tenant


@router.put("/{id}", response_model=WorkspaceOut)
def update_workspace(
    id: str,
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Tenant:
    tenant_id = uuid.UUID(id)
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id, Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if payload.name is not None:
        tenant.name = payload.name
    if payload.plan is not None:
        tenant.plan = payload.plan

    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> None:
    tenant_id = uuid.UUID(id)
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id, Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")

    db.query(Project).filter(Project.tenant_id == tenant.id).delete(synchronize_session=False)
    db.delete(tenant)
    db.commit()
