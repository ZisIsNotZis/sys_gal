# mail/

Doorstep for this layer. A message waits in the receiver's `mail/`, under version control, and is deleted by the receiver once its content has landed.

## Shape

Five header lines, then the body, then the effort at the end of the same file:

```text
kind:    resource | cost | direction | contract | report
from:    <layer that wrote it>
to:      root | person | sys_gal | <package name>
spend:   <class: person_attention, person_time, machine_time, money, exclusive, irreversible, trust>
id:      <what it answers or asks; `none` plus where it is answered if the run report carries it>

<body: the question or the order>

<effort: what it costs the receiver to answer, for kind direction and cost>
```

`to` is carried in addition to the four fields the law requires, because `root` and `person` mail for this directory share `mail/`; without it a reader cannot tell who must act.

## Conventions

- File name: `YYYY-MM-DD-<subject>.md`. A report keeps the id of the contract it answers.
- A report upward carries three things: whose roadmap changes, an evidence pointer, and the decision needed, which may be `none`.
- `from: person` mail is forwarded upward unchanged and never answered here.
- Delete after landing; deletion is tidying and is not a receipt.
