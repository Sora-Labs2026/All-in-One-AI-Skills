# Embedded firmware

Read this before writing or changing firmware for microcontrollers: bare-metal C or C++, an RTOS (FreeRTOS, Zephyr), vendor SDKs (STM32Cube, ESP-IDF, nRF Connect, Pico SDK), Arduino or PlatformIO projects, embedded Rust. General C++ practice is in `cpp.md`, memory-safety review in `../../code-security-review/references/c-and-cpp.md`.

## Safety first

Firmware drives real hardware: motors, heaters, relays, batteries, radios. A wrong register write can damage a board or hurt someone.

- **Never flash a device, change fuses or option bytes, write to a bootloader, or run code that moves actuators without the user's explicit go-ahead for that step.** Build, run host tests and simulate first; hand the user the exact flash command.
- Do not change clock trees, power regulators, brown-out levels, watchdog or memory-protection settings as a side effect of another change.
- Treat datasheets, reference manuals and errata sheets as the specification. When the code and the datasheet disagree, stop and ask; say which document revision you read.
- Safety-related products (medical, automotive, industrial control) follow standards such as IEC 61508, ISO 26262 or IEC 62304 with processes this guide does not replace; flag that to the user.

## Orient first

| Signal | Toolchain | Build |
|---|---|---|
| `platformio.ini` | PlatformIO environments per board | `pio run -e <env>`; host tests `pio test -e native` |
| `west.yml`, `prj.conf`, `boards/` overlays | Zephyr with west | `west build -b <board> <app>` |
| `sdkconfig`, `idf_component.yml`, `main/CMakeLists.txt` | ESP-IDF | `idf.py build` |
| `*.ioc` and `Core/`, `Drivers/` folders | STM32CubeMX-generated code | CMake or the IDE's makefile; regenerate from the `.ioc` file, never hand-edit generated sections outside `USER CODE` markers |
| `memory.x`, `.cargo/config.toml` with a `thumbv*` target | Embedded Rust (cortex-m, Embassy, RTIC) | `cargo build --release`; flashing and debugging with probe-rs |
| `*.ld` linker script, `startup_*.s`, a cross toolchain file | Bare metal with GCC or Clang for Arm, RISC-V or others | The project's CMake or Make |

Record the MCU part number, clock frequency, flash and RAM sizes, the toolchain version, and the SDK or RTOS version before writing code. Vendor SDK APIs change between major versions.

## Constraints shape the code

- **Memory budget:** read the linker map file (`-Wl,-Map=out.map`) or `arm-none-eabi-size` output before and after a change, and report the delta in flash and RAM.
- **No dynamic allocation after initialization** unless the project already allows it. Heap fragmentation on a device that runs for months is a field failure. Use static buffers, fixed-size pools, RTOS static creation APIs (`xTaskCreateStatic`, `xQueueCreateStatic`) or Zephyr's static definitions.
- **Stack sizes are fixed per task.** Measure, do not guess: FreeRTOS `uxTaskGetStackHighWaterMark`, Zephyr's thread analyzer, or GCC's `-fstack-usage` per function. Avoid large local arrays, recursion and `printf`-family calls in small tasks.
- **Floating point:** check whether the core has an FPU and whether the build uses it (`-mfloat-abi=hard`, `-mfpu=...`); without one, floating point is slow software emulation. Fixed-point arithmetic is common in control loops.
- **Timing:** know each loop's deadline and worst-case execution time; measure with a GPIO toggle on a logic analyzer or the cycle counter (DWT on Cortex-M), not with log statements.

## Interrupts and shared data

- **Keep interrupt handlers short:** read or clear the hardware status, move data into a buffer, signal a task, return. No blocking calls, no heap, no `printf`, no long loops.
- Variables shared between an interrupt and the main code or tasks are `volatile` (so the compiler reloads them), **and** accesses that are not a single atomic read or write are protected. `volatile` gives no atomicity and no ordering between variables.
- Protect multi-step updates with a short critical section (disable the relevant interrupt or use the RTOS critical-section API), or use a single-producer single-consumer ring buffer with atomic index updates.
- Clear interrupt flags correctly for the peripheral (some clear on read, some on write-one-to-clear); a flag left set re-enters the handler forever.
- Interrupt priorities: on Cortex-M with FreeRTOS, a handler that calls RTOS functions must have a logical priority at or below `configMAX_SYSCALL_INTERRUPT_PRIORITY`. On Cortex-M a lower logical priority is a numerically higher value, and priority 0 (the reset default) is the most urgent, so it is not allowed for such handlers. Getting this wrong corrupts the kernel at random; `configASSERT` catches it in debug builds.

## RTOS tasks

- One task per independent activity with its own timing (sensor sampling, communication, control loop, UI), not one per function.
- Communicate with queues, stream or message buffers, and task notifications rather than shared globals. From interrupts, use only the ISR-safe variants (`...FromISR` in FreeRTOS, with the yield-request argument handled).
- **Mutexes, not binary semaphores, for shared resources**, so priority inheritance limits priority inversion. Never take a mutex in an interrupt. Keep lock order consistent across tasks.
- No busy-waiting; block on a queue, notification or delay. `vTaskDelayUntil` (or `k_timer`/`k_sleep` with absolute timing) for periodic loops, so jitter does not accumulate.
- Enable the RTOS's checks in debug builds: stack overflow detection (`configCHECK_FOR_STACK_OVERFLOW`), `configASSERT`, malloc-failed hooks.

## Peripherals and buses

| Bus | Common failure | Practice |
|---|---|---|
| I2C | Bus stuck low after a reset mid-transfer; missing pull-ups; wrong 7-bit versus 8-bit address | Bus recovery (clock out nine pulses) at init; check every transfer's return code; timeouts on every wait |
| SPI | Wrong clock polarity or phase (mode); chip select timing | Set the mode from the device datasheet; one owner per bus or a bus mutex; DMA for large transfers |
| UART | Overruns at high baud rates; framing errors ignored | Interrupt or DMA reception into a ring buffer; handle error flags; protocol-level checksums and timeouts |
| CAN | Bus-off after errors; unfiltered traffic floods the CPU | Hardware acceptance filters; bus-off recovery policy; respect the network's ID allocation |

- Every hardware wait has a timeout and an error path; `while (!(REG & FLAG));` hangs forever when the hardware misbehaves.
- Use DMA for streams, and mind cache coherency on cores with data caches (clean or invalidate buffers, or place them in non-cacheable memory).
- Read the errata sheet for every peripheral you touch.

## Reliability

- **Watchdog:** enabled in production builds, fed from a place that proves the system is healthy (for example, the main loop after every task has checked in), never from a timer interrupt alone.
- Record the reset cause at boot (watchdog, brown-out, software reset, power-on) and keep it for diagnostics.
- Fault handlers (HardFault and friends) capture registers and the stack pointer to a persistent area, then reset safely.
- Persistent data in flash or EEPROM: wear leveling, a version and a checksum on every record, and writes that survive power loss (write the new copy, then switch a pointer or sequence number).
- Firmware updates: an A/B or bootloader-managed scheme with image verification (signature or at least a checksum) and rollback; never brick the device on a failed update.

## Power

- Measure current with a power analyzer or a current-sense setup, in each operating mode, before and after.
- Sleep whenever there is no work: the RTOS tickless idle mode, or the MCU's stop and standby modes with wake-up sources configured. Gate clocks of unused peripherals; configure unused pins as analog or with defined pulls so they do not float.
- Batch radio and sensor activity; every wake-up costs energy beyond the work itself.

## Testing

- **Host unit tests** for logic that does not touch registers: protocol parsers, state machines, filters, ring buffers. Unity, CppUTest or GoogleTest on the development machine, with the hardware access layer behind an interface replaced by fakes.
- **Static analysis:** compiler warnings at `-Wall -Wextra` treated as errors in new code, cppcheck or clang-tidy, and a MISRA C or C++ checker if the project is bound to that guideline (MISRA checkers are commercial; use the one licensed).
- **Emulation:** QEMU or Renode for supported boards to run firmware in CI without hardware.
- **Hardware-in-the-loop:** tests on a real board through a debug probe or test fixture, run by the user or a lab rig they control. Report which tests ran on hardware and which only on the host.

## Done when

- [ ] The firmware builds for every configured target with no new warnings, and the flash and RAM delta is reported from the map or size output.
- [ ] Host unit tests pass for changed logic; emulation or hardware tests are reported as run, or as `NOT VERIFIED` with the reason.
- [ ] Interrupt handlers stay short; shared data is `volatile` where needed and protected for multi-step access; RTOS calls from interrupts use ISR-safe APIs.
- [ ] Every hardware wait has a timeout; stack usage of changed tasks was measured or estimated with `-fstack-usage`.
- [ ] Nothing was flashed, and no fuse, option byte or actuator was touched, without the user's go-ahead.
