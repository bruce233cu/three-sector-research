"""V2.2 §8 legal transition kernel, checkpoints and immutable lifecycles.

The kernel consumes explicit rule evidence. It cannot certify missing business
definitions: the production rule adapter leaves those predicates unknown.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, asdict, field
from uuid import uuid5, NAMESPACE_URL

ALLOWED={'S0':{'S0','S1'},'S1':{'S0','S1','S2'},'S2':{'S2','S3'},
         'S3':{'S2','S3','S4'},'S4':{'S4'}}


def validate_transition(previous, current, *, new_lifecycle=False):
    if previous=='S4' and current=='S1' and new_lifecycle:
        return
    if previous not in ALLOWED or current not in ALLOWED[previous]:
        raise ValueError('illegal frozen state transition: '+str(previous)+'->'+str(current))


@dataclass
class Checkpoint:
    object_id: str
    rule_version: str
    parameter_profile: str
    metric_availability_version: str
    state: str | None = None
    last_date: str | None = None
    state_days: int = 0
    consecutive: dict = field(default_factory=lambda:{'confirm':0,'weaken':0,'retire':0})
    lifecycle: dict | None = None
    prior_lifecycle_id: str | None = None
    reentry_count: int = 0
    freeze_started_at: str | None = None
    freeze_ended_at: str | None = None
    freeze_active: bool = False
    counter_policy: str | None = None


def advance(checkpoint, snapshot, evaluation, profile, market_dates, *, resume_policy=None):
    """Daily pure function. Same input => identical state/UUID/output/checkpoint.

    resume_policy defaults UNRESOLVED: frozen V2.2 has no counting/resume rule.
    Explicit reset can be exercised by fixtures, never silently set in live mode.
    A missing previous checkpoint is unknown, never fabricated as historical S0.
    """
    cp=deepcopy(checkpoint)
    completed=profile.get('clarification_version') == 'V2.2.1-mainline-state-completion-2026-10-02'
    if completed:
        cp.consecutive.setdefault('recover',0)
    resume_day=False
    day=str(snapshot['as_of_date']);calendar=sorted(str(d) for d in market_dates)
    identity=(snapshot['object_id'],snapshot['rule_version'],profile['profile_id'],snapshot['metric_availability_version'])
    if identity!=(cp.object_id,cp.rule_version,cp.parameter_profile,cp.metric_availability_version):
        raise ValueError('checkpoint object/version/profile mismatch')
    if len(calendar)!=len(set(calendar)) or day not in calendar:
        raise ValueError('invalid target market date')
    if cp.last_date:
        if cp.last_date not in calendar or calendar.index(day)!=calendar.index(cp.last_date)+1:
            raise ValueError('checkpoint must precede target by one market session')
    evidence=evaluation['evidence'];previous=cp.state;transition=None;reason=None
    if any(v is not None and type(v) is not bool for v in evidence.values()):
        raise ValueError('rule evidence must be bool or NULL')
    quality_bad=not snapshot.get('critical_data_ok',False) or snapshot.get('stage_frozen',False)
    frozen=quality_bad;debounce_status='not_pending';debounce_reason=None;debounce_days=0
    resume_reason=None
    if previous is None:
        frozen=True;reason='trusted_previous_state_missing'
    elif quality_bad:
        if not cp.freeze_active or cp.freeze_ended_at is not None:
            cp.freeze_started_at=day
            cp.freeze_ended_at=None
        cp.freeze_active=True
        if completed: cp.counter_policy='paused'
        reason=snapshot.get('freeze_reason') or 'critical_data_unavailable'
        debounce_status='paused_by_freeze';debounce_reason='no_new_hard_transition';debounce_days=max(cp.consecutive.values())
    else:
        if cp.freeze_active:
            if cp.freeze_ended_at is None:
                cp.freeze_ended_at=day
            if completed:
                from .replay import verified_freeze_gap
                gap=calendar[calendar.index(cp.freeze_started_at):calendar.index(day)]
                proof=snapshot.get('freeze_gap_evidence',[])
                verified=len(gap)<=3 and verified_freeze_gap(proof,gap,cp)
                cp.counter_policy='resumed' if verified else 'reset_after_unverifiable_gap'
                if not verified: cp.consecutive={k:0 for k in cp.consecutive}
                cp.freeze_active=False;resume_day=True
                resume_reason=cp.counter_policy
            elif resume_policy is None:
                frozen=True;reason='BUSINESS_RULE_CONFLICT:freeze_resume_count_policy_missing'
                resume_reason='data_restored_state_resume_policy_unresolved'
            elif resume_policy=='reset':
                cp.consecutive={k:0 for k in cp.consecutive};cp.freeze_active=False
                resume_reason='explicit_fixture_resume_policy_reset'
            else:
                raise ValueError('unsupported resume policy')
        if not frozen:
            state=previous;trigger=None
            required={'S0':['candidate'],'S1':['confirm','candidate'],'S2':['weaken'],
                      'S3':['retire','recover'],'S4':['candidate']}[previous]
            # Do not use Python bool(None) anywhere in evidence evaluation.
            if any(evidence[k] is None for k in required):
                frozen=True;reason='rule_evidence_unavailable:'+','.join(k for k in required if evidence[k] is None)
            else:
                for key in cp.consecutive:
                    eligible={'confirm':previous=='S1','weaken':previous=='S2','retire':previous=='S3','recover':previous=='S3'}[key]
                    cp.consecutive[key]=(cp.consecutive[key]+1 if eligible and evidence[key] is True else 0)
                if resume_day:
                    reason='freeze_recovery_first_session_no_transition'
                    debounce_status='recovery_first_day_guard';debounce_reason=reason
                elif previous=='S0' and evidence['candidate']:
                    state='S1';trigger='candidate'
                elif previous=='S1':
                    if cp.consecutive['confirm']>=profile['confirm']['confirm_consecutive_days']:
                        state='S2';trigger='confirm'
                    elif not evidence['candidate']:
                        state='S0';trigger='candidate_failed'
                elif previous=='S2':
                    confirmed_at=cp.lifecycle.get('confirmed_at') if cp.lifecycle else None
                    dwell=(calendar.index(day)-calendar.index(confirmed_at) if confirmed_at in calendar else None)
                    if dwell is None:
                        frozen=True;reason='confirmed_date_missing'
                    elif cp.consecutive['weaken']>=profile['weaken']['consecutive_days'] and dwell>=profile['weaken']['min_dwell_days_after_confirm']:
                        state='S3';trigger='weaken'
                    elif evidence['weaken']:
                        debounce_status='waiting_consecutive_or_dwell';debounce_reason='frozen_minimum_dwell_or_consecutive_days'
                elif previous=='S3':
                    if cp.consecutive['retire']>=profile['retire']['consecutive_days']:
                        state='S4';trigger='retire'
                    elif (cp.consecutive.get('recover',0)>=2 if completed else evidence['recover']):
                        state='S2';trigger='recover'
                elif previous=='S4' and evidence['candidate']:
                    state='S1';trigger='new_lifecycle_reentry'
                if not frozen and state!=previous:
                    new_lifecycle=state=='S1'
                    validate_transition(previous,state,new_lifecycle=new_lifecycle)
                    if new_lifecycle:
                        prior_id=cp.lifecycle['lifecycle_id'] if cp.lifecycle else cp.prior_lifecycle_id
                        if prior_id is not None:
                            cp.reentry_count+=1
                        lid=str(uuid5(NAMESPACE_URL,'|'.join([cp.object_id,cp.rule_version,cp.parameter_profile,day,prior_id or 'first'])))
                        cp.lifecycle={'lifecycle_id':lid,'object_id':cp.object_id,'object_type':snapshot['object_type'],
                            'profile_id':cp.parameter_profile,'start_date':day,'candidate_at':day,'confirmed_at':None,
                            'weakened_at':None,'closed_at':None,'end_date':None,'close_reason':None,
                            'prior_lifecycle_id':prior_id,'current_state':'S1','highest_state':'S1',
                            'last_transition_date':day,'reentry_count':cp.reentry_count}
                    if cp.lifecycle:
                        cp.lifecycle.update(current_state=state,last_transition_date=day,
                            highest_state=max(cp.lifecycle['highest_state'],state))
                        if state=='S2' and cp.lifecycle['confirmed_at'] is None:
                            cp.lifecycle['confirmed_at']=day
                        if state=='S3' and cp.lifecycle['weakened_at'] is None:
                            cp.lifecycle['weakened_at']=day
                        if state in ['S4','S0']:
                            cp.lifecycle.update(closed_at=day,end_date=day,close_reason=trigger)
                            cp.prior_lifecycle_id=cp.lifecycle['lifecycle_id']
                    transition={'from_state':previous,'to_state':state,'trigger_rule':trigger,
                        'trigger_date':day,'effective_date':day,'reason':trigger,
                        'lifecycle_id':cp.lifecycle['lifecycle_id'] if cp.lifecycle else None}
                    cp.state=state;cp.state_days=0;cp.consecutive={k:0 for k in cp.consecutive}
                    reason=trigger
                elif not frozen:
                    reason=reason or 'no_legal_transition_triggered'
                    if previous=='S1' and evidence['confirm']:
                        debounce_status='waiting_consecutive_days';debounce_reason='confirm_requires_two_consecutive_sessions'
                debounce_days=max(cp.consecutive.values())
    if frozen and not cp.freeze_active:
        cp.freeze_started_at=day
        cp.freeze_ended_at=None
        cp.freeze_active=True
        if completed: cp.counter_policy='paused'
    cp.last_date=day
    if cp.state is not None:
        cp.state_days+=1
    result={'trade_date':day,'object_id':cp.object_id,'state':cp.state,'previous_state':previous,
        'state_days':cp.state_days,'lifecycle_id':cp.lifecycle['lifecycle_id'] if cp.lifecycle else None,
        'upgrade_candidate':evidence.get('candidate'),'downgrade_candidate':evidence.get('weaken'),
        'consecutive_days':deepcopy(cp.consecutive),'debounce_status':debounce_status,
        'debounce_days':debounce_days,'debounce_reason':debounce_reason,
        'critical_data_ok':snapshot.get('critical_data_ok',False),'stage_frozen':frozen,
        'freeze_reason':reason if frozen else None,'freeze_started_at':cp.freeze_started_at,
        'freeze_ended_at':cp.freeze_ended_at,'resume_reason':resume_reason,
        'rule_version':cp.rule_version,'parameter_profile':cp.parameter_profile,
        'metric_availability_version':cp.metric_availability_version,
        'clarification_version':profile.get('clarification_version'),
        'counter_policy':cp.counter_policy,
        'trigger_rules':evaluation.get('trigger_rules',[]),'failed_rules':evaluation.get('failed_rules',[]),
        'unavailable_rules':evaluation.get('unavailable_rules',[]),'reason':reason,'transition':transition,
        'run_id':snapshot.get('run_id'),'source_snapshot_ids':snapshot.get('source_snapshot_ids',[]),
        'reentry_count':cp.reentry_count,'checkpoint':asdict(cp)}
    return result,cp

