# Pybricks firmware supporting UARTDevice

## Firmware and Patches

Prebuilt firmware images with the required patches are provided with this project.

### Flashing the Firmware

To flash a patched firmware onto your device, use the **Pybricks firmware update tool**:

1. Open the Pybricks firmware updater:  
   https://code.pybricks.com

2. Select your platform and follow the instructions to put the device into **firmware update mode**.

3. In the firmware update dialog, enable **Advanced options**.

4. Select **Use local firmware file** (or equivalent).

5. Browse to and select the patched firmware file provided in this repository.

6. Start the update and wait until flashing is complete.

### Local Repository Requirement

The firmware files are **not fetched automatically**.  
This repository must be **cloned or downloaded locally** so the firmware file can be selected from your filesystem during the update process.

Make sure you are using the firmware version that matches your device.

# Firmware patches

## EV3

The newest EV3 firmware already has `UARTDevice` enabled in the the latest firmware. 

## SPIKE Prime
This firmware was compiled with the option

`#define PYBRICKS_PY_IODEVICES_UART_DEVICE       (1)`

added to `mpconfigport.h`

Furthermore, the code has been changed to always enable power on pin 2 of the LPF2 port. This was done by adding the following code to `pybricks/iodevices/pb_type_uart_device.c`:


```
 // Get device, which inits UART port
    pb_type_uart_device_obj_t *self = mp_obj_malloc(pb_type_uart_device_obj_t, >

...


 // enable power on p2
    pbio_port_p1p2_set_power(self->port, PBIO_PORT_POWER_REQUIREMENTS_BATTERY_VOLTAGE_P2_POS);
 // line above was added	

    // Awaitables associated with reading and writing.
    self->write_iter = NULL;
    self->read_iter = NULL;
    self->wait_len = 0;

    return MP_OBJ_FROM_PTR(self);
}

```

## Technik hub

Recompiled the firmware with the option

`#define PYBRICKS_PY_IODEVICES_UART_DEVICE       (1)`

added to `mpconfigport.h`


