import os
from sqlalchemy import create_engine, Column, Integer, String, Date, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import date

# The engine now checks for a cloud URL first. If it doesn't find one, it falls back to your local Docker.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:ascend_admin@localhost:5432/ascend_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    total_xp = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    current_streak = Column(Integer, default=0, nullable=False)
    ascension_tier = Column(String, default="Iron", nullable=False)
    streak_freezes = Column(Integer, default=2, nullable=False)
    last_active_date = Column(Date, default=date.today, nullable=False)

class Habit(Base):
    __tablename__ = "habits"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    icon = Column(String, default="🎯")
    color_hex = Column(String, default="#636EFA")
    time_block = Column(String, default="Morning")
    difficulty = Column(String, default="Medium")
    priority = Column(String, default="Medium")
    created_at = Column(Date, default=date.today)
    is_active = Column(Boolean, default=True)

class CompletionLog(Base):
    __tablename__ = "completion_logs"
    id = Column(Integer, primary_key=True, index=True)
    habit_id = Column(Integer, nullable=False)
    date_completed = Column(Date, default=date.today)


def init_db():
    Base.metadata.create_all(bind=engine)

    # create_all() never alters existing tables — patch missing columns manually.
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    existing_cols = {c["name"] for c in inspector.get_columns("users")}

    migrations = {
        "streak_freezes": "ALTER TABLE users ADD COLUMN streak_freezes INTEGER DEFAULT 2 NOT NULL",
        "ascension_tier": "ALTER TABLE users ADD COLUMN ascension_tier VARCHAR DEFAULT 'Iron' NOT NULL",
        "current_streak": "ALTER TABLE users ADD COLUMN current_streak INTEGER DEFAULT 0 NOT NULL",
        "last_active_date": f"ALTER TABLE users ADD COLUMN last_active_date DATE DEFAULT '{date.today()}' NOT NULL",
    }

    with engine.begin() as conn:
        for col, ddl in migrations.items():
            if col not in existing_cols:
                conn.execute(text(ddl))

    db = SessionLocal()
    if not db.query(User).first():
        db.add(User(username="Aaryan", total_xp=0, level=1, streak_freezes=2))
        db.commit()
    db.close()


def calculate_tier(level):
    if level >= 100: return "Onyx"
    if level >= 50: return "Gold"
    if level >= 25: return "Silver"
    if level >= 10: return "Bronze"
    return "Iron"


def log_habit_completion(habit_id, user_id=1, local_date=None):
    if local_date is None:
        local_date = date.today()

    db = SessionLocal()
    try:
        if db.query(CompletionLog).filter_by(habit_id=habit_id, date_completed=local_date).first():
            return False

        habit = db.query(Habit).filter(Habit.id == habit_id).first()
        user = db.query(User).filter(User.id == user_id).first()

        if not habit or not user:
            return False

        days_since_last = (local_date - user.last_active_date).days

        if days_since_last == 1:
            user.current_streak += 1
        elif days_since_last > 1:
            missed_days = days_since_last - 1
            if user.streak_freezes >= missed_days:
                user.streak_freezes -= missed_days
                user.current_streak += 1
            else:
                user.current_streak = 1
                user.streak_freezes = 0
        elif days_since_last == 0 and user.current_streak == 0:
            user.current_streak = 1

        user.last_active_date = local_date

        diff_map = {"Easy": 5, "Medium": 10, "Hard": 20}
        base_xp = diff_map.get(habit.difficulty, 10)

        prio_map = {"Low": 1.0, "Medium": 1.5, "High": 2.0}
        prio_mult = prio_map.get(habit.priority, 1.0)

        streak = user.current_streak
        if streak >= 365: streak_bonus = 1.0
        elif streak >= 100: streak_bonus = 0.65
        elif streak >= 60: streak_bonus = 0.50
        elif streak >= 30: streak_bonus = 0.35
        elif streak >= 14: streak_bonus = 0.20
        elif streak >= 7: streak_bonus = 0.10
        else: streak_bonus = 0.0

        habit_age = (local_date - habit.created_at).days + 1
        if habit_age <= 14:
            momentum_bonus = 1.0
        elif habit_age <= 45:
            momentum_bonus = 1.0 - ((habit_age - 14) / 31.0)
        else:
            momentum_bonus = 0.0

        final_xp = int(base_xp * prio_mult * (1.0 + streak_bonus + momentum_bonus))

        user.total_xp += final_xp
        user.level = (user.total_xp // 100) + 1
        user.ascension_tier = calculate_tier(user.level)

        db.add(CompletionLog(habit_id=habit_id, date_completed=local_date))
        db.commit()
        return final_xp
    except Exception as e:
        db.rollback()
        return False
    finally:
        db.close()


def get_user_stats(user_id=1):
    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()
    if user:
        return {
            "total_xp": user.total_xp,
            "level": user.level,
            "current_streak": user.current_streak,
            "ascension_tier": user.ascension_tier,
            "streak_freezes": user.streak_freezes
        }
    return {"total_xp": 0, "level": 1, "current_streak": 0, "ascension_tier": "Iron", "streak_freezes": 2}