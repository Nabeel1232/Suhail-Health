"""Validated operational configuration; minimum clinical safeguards cannot be removed."""
import json
import os
from pathlib import Path
from functools import lru_cache
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .config import ROOT

BASE_EVIDENCE = {'investigation', 'reviewed_outcome', 'patient_updated'}
BASE_MILESTONES = ['result_ingested', 'identity', 'notification', 'acknowledgement', 'understanding',
    'referral', 'appointment', 'attendance', 'investigation', 'reviewed_outcome', 'patient_updated']
ALIASES = {'FIT_POSITIVE': 'FIT_POS', 'FIT+': 'FIT_POS', '58453-2': 'FIT_POS'}


class ServiceWindows(BaseModel):
    model_config = ConfigDict(extra='forbid')
    routine_hours: float = Field(default=48, gt=0, le=8760)
    consultation_hours: float = Field(default=24, gt=0, le=8760)
    handoff_hours: float = Field(default=24, gt=0, le=8760)
    urgent_ack_minutes: float = Field(default=60, gt=0, le=1440)
    source: str = Field(min_length=1)


class PathwayPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    version: str = Field(min_length=1)
    status: str
    test_codes: list[str] = Field(min_length=1)
    endpoint: str
    required_evidence: list[str]
    conditional_evidence: list[str]
    milestones: list[str] = Field(default_factory=lambda: list(BASE_MILESTONES))
    service_windows: ServiceWindows
    default_owner: str = Field(min_length=1)
    backup_queue: str = Field(min_length=1)
    closure_roles: list[str]
    allow_autonomous_closure: bool

    @field_validator('default_owner', 'backup_queue')
    @classmethod
    def nonblank_accountable_queue(cls, value):
        if not value.strip():
            raise ValueError('An accountable team or exception queue is required.')
        return value.strip()

    @model_validator(mode='after')
    def enforce_minimums(self):
        if self.id != 'colorectal-fit':
            raise ValueError('Only the first configured colorectal pathway is implemented.')
        if not BASE_EVIDENCE.issubset(self.required_evidence):
            raise ValueError('Required investigation, clinician outcome review and patient update cannot be removed.')
        if not {'treatment_initiated', 'surveillance_plan'}.issubset(self.conditional_evidence):
            raise ValueError('The declared onward-care endpoint alternatives must remain explicit.')
        if not set(BASE_MILESTONES).issubset(self.milestones):
            raise ValueError('Core independently evidenced milestones cannot be removed.')
        if set(self.milestones) - set(BASE_MILESTONES) - set(self.required_evidence):
            raise ValueError('Additional milestones require a configured evidence type and owned evidence task.')
        if self.allow_autonomous_closure or self.closure_roles != ['clinician']:
            raise ValueError('Only an authorized clinician can record clinical disposition.')
        return self

    def supports(self, code):
        return code in self.test_codes or ALIASES.get(code) in self.test_codes


@lru_cache
def load_policy(path=None):
    source = Path(path or os.environ.get('PATHWAY_POLICY_PATH', ROOT / 'pathways/colorectal-demo/policy.json'))
    return PathwayPolicy.model_validate(json.loads(source.read_text()))
