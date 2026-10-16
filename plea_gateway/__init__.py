"""PLEA gateway, v0.6: the attempt-budget contract v3.1 over a transactional store, with a witness service and verified evidence.

The verified pure reference (plea_budget_ref, sha256 a367a4bb...) is the decision engine.  This package adds what
the contract leaves to the gateway: one locked transaction per operation (G01), durability, an audit hash chain,
a witness whose acceptances are separate transactions and come back signed (receipts), a database-enforced
authority boundary (only the plea_witness role can apply an acceptance), and a gate that crosses once, behind a
verified receipt, and labels on RELEASE and RECONCILE derived by the witness from gate-signed reports (G03), and in v0.4 a gate host that holds the only gate key, runs each
attempt's tool exactly once and signs the reports, so the caller's process holds no key, and in v0.5 mutual TLS
between the governor, the witness service and the gate host (tls.py), and in v0.6 execution authorisation and
recovery (binding.py): CROSS is the admission point before dispatch, the witness's receipt binds the nonce, the
nonce binds executor, tool and arguments, the effect report covers the result, terminal outcomes are stored and
replayed, and admitted work is recovered without a second execution.  No accounting logic lives here: every
decision comes from the reference.
"""
from .store import Store, Decision, SCHEMA, AUTHORITY, AuthorityError, UnknownRoot, RootExists
from .receipts import Receipt, ReceiptInvalid, Signer, verify as verify_receipt
from .evidence import Evidence, GateSigner, OutcomeInvalid, derive_release_label, derive_verdict, verify_effect_report
from .binding import nonce_for, result_digest, canonical
from .witness import Witness, RemoteWitness, WitnessUnavailable
from .governor import Governor, BudgetExhausted, Held, Stopped, InProgress, NoEffect, GovernedError, GateRefusedRun, RequestKeyReused, OutcomeUnavailable, VerdictRefused
from .gate_host import GateHostClient, GateRefused
from .tls import TLSClient, TLSServer, TransportError, init_pki

__all__ = ['Store', 'Decision', 'SCHEMA', 'AUTHORITY', 'AuthorityError', 'UnknownRoot', 'RootExists',
           'Receipt', 'ReceiptInvalid', 'Signer', 'verify_receipt', 'Evidence', 'GateSigner', 'derive_release_label', 'derive_verdict',
           'OutcomeInvalid', 'verify_effect_report', 'nonce_for', 'result_digest', 'canonical', 'RequestKeyReused', 'OutcomeUnavailable', 'VerdictRefused',
           'Witness', 'RemoteWitness', 'WitnessUnavailable',
           'Governor', 'BudgetExhausted', 'Held', 'Stopped', 'InProgress', 'NoEffect', 'GovernedError', 'GateRefusedRun',
           'GateHostClient', 'GateRefused', 'TLSClient', 'TLSServer', 'TransportError', 'init_pki']
