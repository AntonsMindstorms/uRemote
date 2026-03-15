# uRemote for MicroBlocks (MicroRemote)

This library is a stripped-down version of the **UARTRemote** protocol, adapted for **MicroBlocks**.
It provides a simple, reliable command-based communication protocol over UART.

## UARTDevice
This library deploys the Pybricks `UARTDevice` on the Lego hub side. This is an option that is not standard available in the firmwares of the Pybricks hubs. Therefore, you will find firmwares supporting `UARTDevice` in the `pybricks_firmware` directory for EV3, Prime hub and Technic hub. In the README we explain how to flash your hub using the pybricks web installer.

## Supported Data Types

The following data types are supported:

- **Number** (32 bit integer encoded as UTF-8 text)
- **String** (UTF-8)
- **Boolean**
- **ByteArray**

## Protocol Format

Each UART frame has the following structure:



```
<tot_len> <PREAMBLE> <len_cmd> <cmd> [<data_type> <data_len> <data>]
```

### Field Description

- **total_len**  
  Total number of bytes in the frame (including the preamble).

- **PREAMBLE**  
  Fixed synchronization preamble:  

```
<$MU
```

- **cmd_len**  
Length of the command string in bytes.

- **cmd**  
Command name encoded as UTF-8.

- **[ ... ]**  
Zero or more data fields.

### Data Field Format

Each data field consists of:

```
<type> <data_len> <data>
```


- **type**
  - `'N'` — Number  
  - `'S'` — String  
  - `'A'` — ByteArray  
  - `'B'` — Boolean  

- **data_len**  
  Length of the data payload in bytes.

- **data**
  - Number: UTF-8 encoded decimal string
  - String: UTF-8 encoded text
  - Boolean: `0x00` = False, `0x01` = True
  - ByteArray: raw bytes

## Robust Receive Handling

Incoming UART data is read **one byte at a time** until a complete frame is received or a timeout occurs.

- **Overall receive timeout:** `time_out`
- **Inter-byte timeout:** `byte_timeout` (fixed at 10 ms)

### Preamble Validation

- The first 4 bytes of the frame must match the preamble `<$MU`.
- If the preamble is invalid:
  - The UART receive buffer is cleared (`read_all()`).
  - The frame is discarded.

This ensures reliable resynchronization even in the presence of noise, dropped bytes, or partial frames.
