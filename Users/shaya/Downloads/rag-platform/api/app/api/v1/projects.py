from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project
from app.schemas.project import ProjectCreate, ProjectOut
from app.core.security import get_current_user, CurrentUser
from app.services.vector_store import collection_name, ensure_collection

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    project = Project(tenant_id=user.tenant_id, name=payload.name, daily_query_quota=payload.daily_query_quota, qdrant_collection="")
    db.add(project)
    db.flush()
    project.qdrant_collection = collection_name(str(user.tenant_id), str(project.id))
    ensure_collection(project.qdrant_collection)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    return db.query(Project).filter(Project.tenant_id == user.tenant_id).all()
