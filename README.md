# NetBench

![NetBench — builds the lab itself, runs the tests on it and shows what measured what](assets/banner.png)

[![CI](https://github.com/bluelightaura/netbench/actions/workflows/ci.yml/badge.svg)](https://github.com/bluelightaura/netbench/actions/workflows/ci.yml)
[![Report](https://img.shields.io/badge/report-Allure-green)](https://bluelightaura.github.io/netbench/)

[Русская версия](README_RU.md)

Automated tests for network devices on a lab that builds itself: infrastructure,
tests, CI and the report — four layers, each verifiable on its own.

The hardware such tests need is usually the thing you do not have. Here it comes
up as containers from a single topology file, lives exactly as long as the run,
and is torn down even when the tests fail.

## This is a skeleton, on purpose

The project is written as a **worked example of the architecture**, not as a
finished product for one particular network. The way to use it: clone it, throw
out the topologies and profiles that are not yours, put your own in their place,
and get a working lab without designing the layers again.

What it already decides for you:

* **a split into layers** where each is verified separately and replaceable
  whole: if containerlab is not your tool, layer 1 changes and the tests do not;
* **data, not code, for the differences between devices** — what to type lives
  in a profile, not in an `if` inside a test;
* **the bench as a swappable part**: virtual and real benches are described the
  same way, and the suite does not know which one it got;
* **three pipelines over one suite**, so portability is visible rather than claimed;
* **the report as part of the suite**, not an artifact bolted on afterwards.

What you will certainly rewrite: topologies, profiles, the node startup configs
and the checks themselves. There is exactly enough of each to make the shape of
the thing visible.

A test with every convention in it: `suites/_template.py`.

## Addresses in this repository

Node configurations use addresses from `192.0.2.0/24` — the range reserved for
documentation (RFC 5737). It is not routed on the internet and cannot collide
with a live network.

There are no other addresses anywhere, including the sample real bench: that one
uses names under `example.net`. Descriptions of real benches are excluded by
`.gitignore` (`lab/benches/*.local.yml`), and no file holds a password — only the
names of environment variables.

This is not a wish but a checked rule: `tests/test_hygiene.py` fails the run if an
address outside the documentation ranges, a written-down password, or a real
bench description ever appears in the repository.

## Layers

| | what it does | with |
|---|---|---|
| 0 · machine | creates the host everything lives on | Terraform (libvirt) |
| 1 · infrastructure | installs the environment and brings the topology up | Ansible, containerlab, FRRouting |
| 2 · tests | talks to the nodes over SSH and checks the CLI surface | pytest, netmiko |
| 3 · CI | builds the image, raises the bench, runs, tears down | Actions · Jenkins · GitLab |
| 4 · report | shows what was checked and with what | Allure on GitHub Pages |

## Quick start

```sh
pip install -e '.[test]'
pytest tests                        # the harness itself: no bench, half a second

make -C lab up                      # bring the virtual bench up
pytest                              # run everything
make -C lab down
```

`pytest tests` runs anywhere and raises nothing. It checks the harness: that the
bench, topology and profile descriptions agree with each other, that the export
hands tools what they expect, and that nothing has leaked into the repository.
In CI it takes half a minute and catches a typo before anyone spends ten minutes
bringing a bench up for it.

Different hardware, same suite:

```sh
make -C lab up TOPO=dc-fabric       # data centre: a spine and two leaves
pytest --bench virtual-dc

make -C lab up TOPO=cpe-sdwan       # CPE in an SD-WAN
pytest --bench virtual-cpe

pytest --bench real.local --apply   # real devices
```

## Hardware — virtual or real

Layer 1 is not nailed to containerlab. A bench is described by a file, and there
are two kinds:

```yaml
# lab/benches/virtual-l3.yml — comes up by itself, lives for one run
kind: virtual
topology: l3-switches
```
```yaml
# lab/benches/real.local.yml — the devices already exist, you connect to them
kind: real
nodes:
  cpe1: {address: cpe1.example.net, profile: cpe-generic}
```

```sh
pytest --bench virtual-l3          # the virtual bench
pytest --bench real.local --apply  # real devices
```

Real bench descriptions are excluded by `.gitignore` (`*.local.yml`): they hold
addresses and logins. Only `real.example.yml` is committed. Passwords live
nowhere — `BENCH_PASSWORD`, or `BENCH_PASSWORD_<NODE>` per device.

**Real hardware is protected separately.** A test marked `changes_config` always
runs on the virtual bench, and is skipped on live equipment until `--apply` is
added. Someone's service sits behind that configuration, and a run has no
business touching it by accident.

## Where the machine comes from

Every tool here has exactly one job, and not for the sake of neatness:

```
Terraform     creates the host
Ansible       turns the host into a bench
containerlab  brings the topology up
pytest        checks
```

Terraform does not describe the topology — containerlab does, and keeping it in
both places would mean keeping the same thing twice.

```sh
cd infra && terraform init && terraform apply
terraform output ansible_line >> ../lab/provision/inventory.ini
```

The default provider is **libvirt**: local KVM, no cloud bill and no keys in the
repository, and `apply` genuinely completes. The cloud variant sits next to it as
`cloud.tf.example` — it needs its own secrets, and a plan nobody can apply proves
less than a local machine that comes up.

Terraform state is excluded by `.gitignore`: it holds addresses and everything
that was created.

If the machine already exists, layer 0 is simply not needed and `inventory.ini`
is edited by hand.

## Deploying onto a bare machine

One playbook takes a host from "nothing here" to "pytest passes":

```sh
make -C lab deploy                  # Docker, containerlab, venv, node image, Allure
make -C lab deploy-no-allure        # without the JVM: the report needs it, the tests do not
```

Four roles, split by what each installs rather than by order:

| role | what for |
|---|---|
| `docker` | bench nodes are containers |
| `containerlab` | brings a topology up from one file |
| `bench` | venv, project dependencies, the node image |
| `allure` | JRE and the Allure CLI — report only, skipped by tag |

It does not have to be this host: `inventory.ini` defaults to `localhost`, and
adding your own runner or VM is one line.

## Preparing real devices

The virtual bench is built by containerlab: configurations are mounted into the
nodes at start. A real device, on the other hand, already exists and remembers
somebody else's edits — it has to be brought to a known state:

```sh
make -C lab devices-baseline BENCH=real.local   # snapshot "before", apply the baseline
make -C lab devices-restore  BENCH=real.local   # put it back
```

The inventory for this is **not a separate file but the same bench descriptor**:
`lab/provision/inventory.py` reads `lab/benches/<name>.yml` and hands out nodes
grouped by device class. Otherwise addresses would live in two places and drift.

## How the generality holds

The devices differ; the conversation with them does not. The differences are
moved into data instead of being spread through the code.

A **profile** (`lab/profiles/*.yml`) describes how a device differs: its prompt,
how to enter configuration mode, how it complains, what changes in its output by
itself — and which commands to type.

The test asks for a concept, the profile supplies the command:

```python
# not one vendor string in the test
session(name).send_command(cmd(name, "version"))
```
```yaml
# lab/profiles/l3-switch.yml
commands:
  version:        show version
  running_config: show running-config
  interface:      show interface {iface}
  neighbors:      show ip ospf neighbor
  bogus:          definitely-not-a-command
```

Another vendor calls the same concepts something else, and only the profile
changes. A concept the profile does not have (the device cannot do it) means the
test is skipped with an explanation, not failed.

The same idea as in the CLIRunner inventory: no vendor profiles, just keys.

**Capabilities.** The profile lists what a device can do, the suite lists what it
needs:

```python
pytestmark = [pytest.mark.lab, pytest.mark.needs("sdwan")]
```

| profile | capabilities |
|---|---|
| `l3-switch` | cli, config, l2, routing |
| `dc-fabric` | cli, config, l2, l3, routing, evpn, vxlan |
| `cpe-generic` | cli, config, sdwan, tunnels, bfd |

Whatever the bench does not declare is skipped with a reason rather than failed
in red. `suites/common` runs everywhere; `l2`, `dc` and `sdwan` wake up where they
make sense. A new class of hardware is a topology and a profile; the tests are
left alone.

## Where to put tests

In `suites/`. The folder is chosen by which hardware the test is addressed to:

| folder | about | wakes up on |
|---|---|---|
| `common/` | any device with a CLI | all |
| `l2/` | switching: VLANs, trunks, the MAC table | `l3-switch`, `dc-fabric` |
| `dc/` | data centre: EVPN, VXLAN, the fabric | `dc-fabric` |
| `sdwan/` | tunnels, BFD, policy | `cpe-generic` |

The folder is for humans. What actually runs is decided by markers:

```python
pytestmark = [pytest.mark.lab, pytest.mark.regress, pytest.mark.needs("sdwan")]
```

A capability the bench profile does not have means a skip with an explanation,
not a red test. A new class of hardware is a new folder, and nothing needs
configuring.

The sample with every convention in it is `suites/_template.py` (pytest does not
collect it — the name does not start with `test_`). Copy it, rename to
`test_<what about>.py`, edit.

```sh
pytest -m smoke                     # smoke only
pytest -m "regress and not slow"
pytest suites/sdwan                 # one folder
```

## Test cases

There is deliberately no separate test-case document here. It would drift away
from the code — in a month there would be two versions of the truth and nobody
able to say which is real.

The test case lives in the test itself, as Allure annotations, and the report
builds a readable card out of them: epic, feature, story, severity, precondition,
steps, expectation. Next to it sits the transcript of what actually went to the
device.

```python
@allure.epic("Network equipment")
@allure.feature("CLI surface")
@allure.severity(allure.severity_level.CRITICAL)
@allure.description("Precondition… Steps… Expected…")
# @allure.testcase("https://tms.example.com/case/123", "TMS-123")
```

If there is a test management system, the two are linked by number through
`allure.testcase`. The identifier is the only thing duplicated, and it does not
go stale.

## Plugging tools in — optional

The bench is self-sufficient: it checks devices and knows nothing about any
tools. But any tool that speaks CLI can be plugged into it — and that is
**a description, not code**.

```yaml
# lab/tools/clirunner.yml
name: clirunner
binary: clirunner          # not on the system — checks for it are skipped
export: clirunner          # which shape to hand the bench over in
export_as: inventory.conf

checks:
  - title: Sees the bench devices and reaches them
    run: ["-i", "{export}", "status"]
    expect: "доступно"
```

Drop a file like that next to the others and the tool is plugged in; there is
nothing to program. `suites/tools/test_tools.py` collects the checks from every
description.

Addresses are not duplicated: the bench exports itself, in the tool's own format.

```sh
python lab/export.py clirunner > inventory.conf
python lab/export.py cliradar
python lab/export.py traphy
```

For CLIRunner that is a section per device class with the keys from the profile —
`config_enter`, `config_exit`, `save_cmd`, `prompt` — so that a switch does not
get CPE settings. For CLIRadar it is a `config.yml` with `password_env`: the
password comes from the environment rather than sitting in a file.

**The bench has no dependency on any of them.** A tool that is not installed means
a skipped check, with an explanation, exactly like a capability a device does not
have. Absence is not a defect.

## Markers, fixtures, flags

**Markers**

| | |
|---|---|
| `lab` | needs a bench that is up |
| `needs(cap)` | the suite needs a capability from the profile |
| `changes_config` | edits the device; on a real one `--apply` is required |
| `smoke` · `regress` · `slow` | levels |

**Fixtures**

| | |
|---|---|
| `bench` | bench nodes: address, port, profile, capabilities |
| `one` | `one()` any node, `one("cpe")` the first whose name starts that way |
| `every` | `every("leaf")` every node whose name starts that way |
| `bench_spec` | the bench description as it is |
| `is_real` | virtual or real |
| `can` | the capabilities of the whole bench |
| `session` | a session to a node; records the transcript, always closes |

**Flags**

| | |
|---|---|
| `--bench NAME` | which bench to take (wins over `BENCH`) |
| `--apply` | allow edits to a real device |
| `--require-bench` | fail the run if every bench check was skipped |
| `--evidence auto\|always\|never` | when to attach the transcript to the report |

## The report

Allure is not here for decoration. The session to a node records everything that
went out and came back, and the transcript is attached to the step — always on a
failure, and on green runs too with `--evidence always`.

Every run also writes `environment.properties`: which bench, which topology,
whether edits were allowed. A week later a report without that says nothing about
what it was actually run against. `lab/allure/categories.json` sorts the outcomes,
so "the bench was not up" is not filed next to "the device answered wrong".

The same point as in every other tool here: "passed" without evidence is
indistinguishable from "nobody looked".

The Allure generator needs a JVM, so it lives in the CI layer rather than in the
suite: the tests themselves depend only on pytest, netmiko and PyYAML.

## Why FRRouting

Apache licence, the image pulls without an account, and `vtysh` gives a genuine
Cisco-like CLI — exactly the surface tools trip over.

cEOS and SR Linux are closer to live hardware but require registration and their
images cannot be redistributed. Real IOS and JunOS through vrnetlab need nested
virtualisation, which GitHub runners do not have. A beautiful topology that fails
every other time is worse than two nodes that always come up green.

FRR does not run an sshd of its own, and tools arrive over SSH — so the image is
built here (`lab/Dockerfile.frr-ssh`). That is the first thing a bench like this
makes you solve, and it is solved rather than worked around by swapping the
transport.

## Why three pipelines

Actions is the main one: only it gives a green badge and a public run history on
the same page the reader arrives at. `Jenkinsfile` and `.gitlab-ci.yml` run the
same suite so that CI portability is visible rather than claimed.

Each of the three starts with the same cheap step — lint and the offline harness
checks — before anything is raised. A broken descriptor should cost half a
minute, not ten.

## What is checked

Not routing, but that the device answers predictably: the prompt, long output
coming back whole without truncation, a refusal on an unknown command,
configuration applying and rolling back. That is what breaks for tools working
over a CLI, and what cannot be checked against mocks.

## Layout

```
infra/                      layer 0
  main.tf                     the machine for the bench (libvirt)
  variables.tf  outputs.tf
  cloud.tf.example            the cloud variant, if needed
lab/                        layer 1
  topologies/               what to bring up
    l3-switches.clab.yml      two switches and a link
    cpe-sdwan.clab.yml        two CPEs and a controller
  profiles/                 how devices differ — as data
    l3-switch.yml
    cpe-generic.yml
  configs/                  node startup configurations
  benches/                  which bench to take
    virtual-*.yml             comes up by itself
    real.example.yml          the sample for real devices
  provision/                Ansible
    site.yml                  deploy the project onto a machine
    inventory.ini             where to deploy
    roles/                    docker · containerlab · bench · allure
    inventory.py              device inventory from the same bench descriptor
    devices-baseline.yml      bring devices to a known state
    devices-restore.yml       put them back
  Dockerfile.frr-ssh        FRR + sshd: straight into vtysh on login
  tools/                    tool descriptions — optional
  allure/                   defect categories for the report
  export.py                 export the bench in a tool's format
  Makefile                  up/down/status for virtual, baseline/restore for real
conftest.py                 layer 2: bench, profiles, capabilities, sessions
tests/                      checks on the harness itself, no bench needed
suites/                     layer 2: the checks
  common/                     any device with a CLI
  tools/                      tools against the bench, from the descriptions
  l2/                         only where the l2 capability is declared
  dc/                         only where evpn / vxlan is declared
  sdwan/                      only where sdwan is declared
.github/workflows/ci.yml    layer 3, the main one: a matrix over topologies
Jenkinsfile                 layer 3
.gitlab-ci.yml              layer 3
```

## Licence

MIT — see [LICENSE](LICENSE).
