# Lab automation: Opentrons protocols, PyLabRobot and cloud-lab protocol APIs

Read this when code drives laboratory hardware (liquid handlers, plate readers, heater-shakers, thermocyclers, incubators, grippers) or submits experiments to a remote automated lab through its protocol API. Recording results in an electronic lab notebook is in `lab-data-platforms.md`.

**Guardrail.** Robots move, spill, crash and consume samples, reagents and money. Simulate or dry-run first, show the user the deck layout and what will happen, and run anything physical only after the user's explicit go-ahead for that run. The agent never bypasses interlocks, door sensors or error states, and never submits a paid or physical cloud-lab job on its own.

## The safe sequence for any physical run

1. **Logic tests in plain Python:** well maps, volumes, dilution math and tip counts as functions with unit tests.
2. **Simulation:** the vendor simulator or a simulated backend. Read the full log, not only the exit status.
3. **Setup sheet for the human:** deck map (slot, labware, contents and volumes), tips needed per rack, reagents and dead volumes, module states, estimated run time.
4. **Go-ahead:** the user confirms the deck matches the sheet, calibration and labware offsets are current, and approves this run.
5. **First physical run with water** (or buffer) on spare labware; check volumes gravimetrically (weigh the plate before and after) or with a dye and a plate reader.
6. **Real samples,** with the run log, protocol version and deck photo saved with the results.

## Opentrons (OT-2 and Flex): Python Protocol API v2

```python
from opentrons import protocol_api

metadata = {"protocolName": "Normalize plate", "author": "Lab team"}
requirements = {"robotType": "Flex", "apiLevel": "2.20"}   # the highest level the robot's software supports

def add_parameters(parameters):                             # runtime parameters, API level 2.18 and later
    parameters.add_int(variable_name="columns", display_name="Columns", default=12, minimum=1, maximum=12)

def run(protocol: protocol_api.ProtocolContext):
    tips = protocol.load_labware("opentrons_flex_96_tiprack_200ul", "B1")
    src = protocol.load_labware("nest_96_wellplate_200ul_flat", "C1", label="Samples")
    dst = protocol.load_labware("nest_96_wellplate_200ul_flat", "C2", label="Normalized")
    trash = protocol.load_trash_bin("A3")                   # Flex: trash is loaded explicitly (2.16 and later)
    p1000 = protocol.load_instrument("flex_8channel_1000", "left", tip_racks=[tips])
    for col in range(protocol.params.columns):
        p1000.transfer(50, src.columns()[col][0], dst.columns()[col][0], new_tip="always", mix_after=(3, 40))
```

```bash
python -m pip install "opentrons==<robot software version>"   # match the robot's software release
opentrons_simulate normalize.py                               # prints every command; fails on many errors before a run
```

- **API level.** Set it to the highest level the target robot's software supports; behavior changes between levels, and Flex needs 2.15 or later. Check the robot's software version, not the newest docs.
- **Instrument and labware names** must match the robot generation (Flex names differ from OT-2 GEN2 names). Take labware load names from the official labware library; define custom labware with the labware creator and keep the JSON with the protocol.
- **Deck.** OT-2 slots are 1 to 11 with the trash in 12. Flex slots are A1 to D3 plus a staging column (A4 to D4); the thermocycler occupies fixed slots on both. The gripper moves labware on Flex with `protocol.move_labware(plate, "D2", use_gripper=True)`.
- **Modules.** The heater-shaker must close its labware latch before shaking; the thermocycler lid must be open for pipetting; temperature changes take minutes, so start them early and wait explicitly.
- **Volumes.** Stay inside each pipette's specified range and prefer the smallest pipette that covers the volume; volumes near a pipette's minimum are inaccurate. `transfer` splits volumes above the maximum into several moves and can use many tips; count them in the simulation log.
- **Liquids.** Set aspirate height (`well.bottom(z=1)`), flow rates, air gaps, blow-out and touch-tip for the liquid: viscous, volatile, foaming and cell-containing liquids each need different settings. Newer API levels add liquid classes; check what the installed level offers. Reservoirs need dead volume; plan for evaporation in long runs.
- **Multichannel pipettes** address row A of a column (`plate.columns()[i][0]`); partial-tip layouts change which nozzles are used and need the matching tip-rack setup.
- **Calibration offsets** from the labware position check live on the robot and in the app; the command-line simulator does not apply them, so a clean simulation does not prove positions are right.
- `protocol.pause("message")` gives the operator a checkpoint (for example to add an enzyme); `protocol.comment` writes to the run log. Do not use `protocol.is_simulating()` to change what the protocol does on the robot.

## PyLabRobot: one Python interface across vendors

PyLabRobot drives Hamilton STAR and STARlet, Tecan EVO, Opentrons OT-2 and many plate readers, heater-shakers, centrifuges, incubators and pumps through swappable backends, with an asynchronous API.

```python
import asyncio
from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.liquid_handling.backends import LiquidHandlerChatterboxBackend   # prints commands, moves nothing
from pylabrobot.resources import STARLetDeck, set_tip_tracking, set_volume_tracking

async def main():
    set_tip_tracking(True)
    set_volume_tracking(True)                       # errors on aspirating more than a well holds
    lh = LiquidHandler(backend=LiquidHandlerChatterboxBackend(num_channels=8), deck=STARLetDeck())
    await lh.setup()
    try:
        ...                                         # assign carriers, plates and tip racks, then pick up, aspirate, dispense
    finally:
        await lh.stop()

asyncio.run(main())
```

- Develop against the chatterbox backend and the browser visualizer, with tip and volume tracking on; swap in the hardware backend only for the approved run.
- Resource definitions (carriers, plates, tip racks) are vendor catalog items with exact dimensions; a wrong definition crashes tips into labware. Verify each definition against the labware actually on the deck.
- Class and module names have changed between releases (backend classes were renamed, visualizer imports moved). Check the installed version and its docs.
- Treat any backend exception as a stop: do not retry motion commands automatically, and leave recovery to the operator.

## Cloud-lab protocol APIs

A cloud lab runs your experiment on its own automation: you submit a protocol or design (sequences, plate maps, assay parameters), it returns data days or weeks later, and each submission costs money.

- **Start from the provider's validated assays and limits:** sequence length, sample count, controls, turnaround and price per sample. Request a quote or feasibility check before submitting.
- **Submission is a purchase and a physical action.** Show the user the exact payload, cost and terms, and submit only on explicit approval of that order. Use the provider's test or sandbox environment for integration work.
- **Idempotency:** send a client reference or idempotency key so a network retry cannot create a duplicate order; check order status before resubmitting.
- **Status and results:** poll with backoff or receive webhooks, verifying signatures (`../../integrations/references/webhooks.md`). Store the order ID, protocol version, input file checksums and the provider's run metadata with the results.
- **Biosafety and confidentiality:** providers screen sequences for hazardous agents; never attempt to evade screening or split a sequence of concern across orders. Read who owns submitted designs and data and how long they are kept before sending proprietary sequences.
- **Credentials** are referenced by name and never printed or committed (`../../agent-safety/GUIDE.md`).

## Records

- Keep protocols in version control; record the API level, robot software version, labware definitions, deck photo, operator, reagent lot numbers and the run log with each dataset.
- Link each run to its notebook entry and sample IDs (`lab-data-platforms.md`).

## Checks (done when)

- Logic tests pass; the simulation log was read and shows the expected tip count, volumes within range, and no warnings left unexplained.
- The user received a deck map and setup sheet and gave an explicit go-ahead before any physical run.
- A water run was checked gravimetrically or photometrically before real samples.
- Cloud-lab orders were quoted, approved by the user, submitted once with an idempotency key, and tracked by order ID.
- Protocol version, software versions and run logs are stored with the results.
