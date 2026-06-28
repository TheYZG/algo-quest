"""
用户认证 API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.all import (
    UserRegister,
    UserLogin,
    TokenResponse,
    UserProfile,
)
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已被占用",
        )

    # 检查邮箱
    if data.email:
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="邮箱已被注册",
            )

    # 创建用户
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 生成 token
    token = create_access_token(user.id)

    return TokenResponse(
        access_token=token,
        user=UserProfile.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    token = create_access_token(user.id)

    return TokenResponse(
        access_token=token,
        user=UserProfile.model_validate(user),
    )


@router.get("/me", response_model=UserProfile)
async def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserProfile.model_validate(user)


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """获取平台统计"""
    # 总用户数
    result = await db.execute(select(func.count()).select_from(User))
    total_users = result.scalar() or 0

    # 总提交数
    from app.models.submission import Submission
    result = await db.execute(select(func.count()).select_from(Submission))
    total_submissions = result.scalar() or 0

    # AC 数
    result = await db.execute(
        select(func.count()).select_from(Submission).where(
            Submission.status == "accepted"
        )
    )
    total_accepted = result.scalar() or 0

    # 从 ChromaDB 获取题目总数
    from app.vectordb import get_collection_stats
    chroma_stats = get_collection_stats()

    return {
        "total_users": total_users,
        "total_problems": chroma_stats["count"],
        "total_submissions": total_submissions,
        "total_accepted": total_accepted,
    }
