from enum import Enum


REVIEWER_ASSIGNMENTS_COLLECTION = "reviewer_assignments"
REVIEWER_EVIDENCE_COLLECTION = "reviewer_evidence"
REVIEWER_RECOMMENDATIONS_COLLECTION = "reviewer_recommendations"
REVIEWER_PROJECTS_COLLECTION = "reviewer_projects"


class ReviewerAssignmentStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ReviewerTaskKind(str, Enum):
    PROJECT = "project"
    EVIDENCE_REVIEW = "evidence_review"
    OTHER = "other"


class ReviewerRecommendation(str, Enum):
    ACCEPT = "ACCEPT"
    REWORK = "REWORK"

