\## Problem description

The UARTDevice iodevice is a nice generic way to communicate with external devices using plain uart communciation. When external devices have more power needs than the 3v3 line can deliver (e.g. when driving NeoPixels or Servo motors), it would be nice when such a device can use 8V power coming from one of the power lines P1 or P2.



The PUPDevice iodevice allows for setting power on either P1 or P2 depending how that is negotiatied in the PUP protocol. For I2CDevices, there is a keyword argument `powered` that allows for powering P1 (not P2). Unfortunately, I2Cdevice is not present for prime hub or technic hub, only for EV3 hub (and there the `powered` does work, but is not effective, as the P1 pin is connected through a 330Ohm resistor, and the voltage drops sharply when connecting a device that draws some current.)



\## Proposed solution 

I propose to add a keyword argument `power\_pin` to the UARTDevice  `\_\_init\_\_` method where the argument can be 0 (no power), 1 (P1 powered) or 2 (P2 powered).



In a pybricks program that would look like:

```

uart = UARTDevice(Port.A, power\_pin = 1)

```



resulting in P1 powered and



```

uart = UARTDevice(Port.A, power\_pin = 0)

```

resulting in P1 nor P2 powered.



\## Proposed changes to `pb\_type\_uart\_device.c` 



\- an extra keyword argument `power\_pin` is added to `\_\_init\_\_`



```

static mp\_obj\_t pb\_type\_uart\_device\_make\_new(const mp\_obj\_type\_t \*type, size\_t n\_args, size\_t n\_kw, const mp\_obj\_t \*args) {

&#x20;   PB\_PARSE\_ARGS\_CLASS(n\_args, n\_kw, args,

&#x20;       PB\_ARG\_REQUIRED(port),

&#x20;       PB\_ARG\_DEFAULT\_INT(baudrate, 115200),

&#x20;       PB\_ARG\_DEFAULT\_NONE(timeout),

&#x20;       PB\_ARG\_DEFAULT\_INT(power\_pin, 0)

&#x20;       );

```

\- depending on the value of `power\_pin` the corresponding pin is powered, or none, when not 1 or 2.

```

&#x20;   if (mp\_obj\_get\_int(power\_pin\_in) == 1) {

&#x20;      pbio\_port\_p1p2\_set\_power(self->port, PBIO\_PORT\_POWER\_REQUIREMENTS\_BATTERY\_VOLTAGE\_P1\_POS);

&#x20;   } else if (mp\_obj\_get\_int(power\_pin\_in) == 2) {

&#x20;      pbio\_port\_p1p2\_set\_power(self->port, PBIO\_PORT\_POWER\_REQUIREMENTS\_BATTERY\_VOLTAGE\_P2\_POS);

&#x20;   } else

&#x20;      pbio\_port\_p1p2\_set\_power(self->port, PBIO\_PORT\_POWER\_REQUIREMENTS\_NONE);

```



<details>

<summary> Click triangle to see the full code with changes for pb\_type\_uart\_device.c </summary>



```

/pybricks-micropython/pybricks/iodevices/pb\_type\_uart\_device.c

```



```

// SPDX-License-Identifier: MIT

// Copyright (c) 2018-2025 The Pybricks Authors



\#include "py/mpconfig.h"



\#if PYBRICKS\_PY\_IODEVICES



\#include "py/mphal.h"

\#include "py/objstr.h"

\#include "py/runtime.h"



\#include <pbdrv/uart.h>

\#include <pbio/port\_interface.h>



\#include <pybricks/common.h>

\#include <pybricks/parameters.h>

\#include <pybricks/tools/pb\_type\_async.h>



\#include <pybricks/util\_mp/pb\_kwarg\_helper.h>

\#include <pybricks/util\_mp/pb\_obj\_helper.h>

\#include <pybricks/util\_pb/pb\_error.h>



// pybricks.iodevices.uart\_device class object

typedef struct \_pb\_type\_uart\_device\_obj\_t {

&#x20;   mp\_obj\_base\_t base;

&#x20;   pbio\_port\_t \*port;

&#x20;   pbdrv\_uart\_dev\_t \*uart\_dev;

&#x20;   uint32\_t timeout;

&#x20;   pb\_type\_async\_t \*write\_iter;

&#x20;   mp\_obj\_t write\_obj;

&#x20;   pb\_type\_async\_t \*read\_iter;

&#x20;   mp\_obj\_str\_t \*read\_obj;

&#x20;   const byte \*wait\_data;

&#x20;   size\_t wait\_len;

} pb\_type\_uart\_device\_obj\_t;



// pybricks.iodevices.UARTDevice.set\_baudrate

static mp\_obj\_t pb\_type\_uart\_device\_set\_baudrate(mp\_obj\_t self\_in, mp\_obj\_t baudrate\_in) {

&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);



&#x20;   int32\_t baud\_rate = pb\_obj\_get\_int(baudrate\_in);

&#x20;   if (baud\_rate < 1) {

&#x20;       pb\_assert(PBIO\_ERROR\_INVALID\_ARG);

&#x20;   }

&#x20;   pbdrv\_uart\_set\_baud\_rate(self->uart\_dev, baud\_rate);

&#x20;   return mp\_const\_none;

}

static MP\_DEFINE\_CONST\_FUN\_OBJ\_2(pb\_type\_uart\_device\_set\_baudrate\_obj, pb\_type\_uart\_device\_set\_baudrate);





// pybricks.iodevices.UARTDevice.\_\_init\_\_

static mp\_obj\_t pb\_type\_uart\_device\_make\_new(const mp\_obj\_type\_t \*type, size\_t n\_args, size\_t n\_kw, const mp\_obj\_t \*args) {

&#x20;   PB\_PARSE\_ARGS\_CLASS(n\_args, n\_kw, args,

&#x20;       PB\_ARG\_REQUIRED(port),

&#x20;       PB\_ARG\_DEFAULT\_INT(baudrate, 115200),

&#x20;       PB\_ARG\_DEFAULT\_NONE(timeout),

&#x20;       PB\_ARG\_DEFAULT\_INT(power\_pin, 0)

&#x20;       );

&#x20;   // Get device, which inits UART port

&#x20;   pb\_type\_uart\_device\_obj\_t \*self = mp\_obj\_malloc(pb\_type\_uart\_device\_obj\_t, type);



&#x20;   if (timeout\_in == mp\_const\_none) {

&#x20;       // In the uart driver implementation, 0 means no timeout.

&#x20;       self->timeout = 0;

&#x20;   } else {

&#x20;       // Timeout of 0 is often perceived as partial read if the requested

&#x20;       // number of bytes is not available. This is not supported, so don't

&#x20;       // make it appear that way.

&#x20;       if (pb\_obj\_get\_int(timeout\_in) < 1) {

&#x20;           pb\_assert(PBIO\_ERROR\_INVALID\_ARG);

&#x20;       }

&#x20;       self->timeout = pb\_obj\_get\_int(timeout\_in);

&#x20;   }



&#x20;   pbio\_port\_id\_t port\_id = pb\_type\_enum\_get\_value(port\_in, \&pb\_enum\_type\_Port);

&#x20;   pb\_assert(pbio\_port\_get\_port(port\_id, \&self->port));

&#x20;   pbio\_port\_set\_mode(self->port, PBIO\_PORT\_MODE\_UART);



&#x20;   if (mp\_obj\_get\_int(power\_pin\_in) == 1) {

&#x20;      pbio\_port\_p1p2\_set\_power(self->port, PBIO\_PORT\_POWER\_REQUIREMENTS\_BATTERY\_VOLTAGE\_P1\_POS);

&#x20;   } else if (mp\_obj\_get\_int(power\_pin\_in) == 2) {

&#x20;      pbio\_port\_p1p2\_set\_power(self->port, PBIO\_PORT\_POWER\_REQUIREMENTS\_BATTERY\_VOLTAGE\_P2\_POS);

&#x20;   } else

&#x20;      pbio\_port\_p1p2\_set\_power(self->port, PBIO\_PORT\_POWER\_REQUIREMENTS\_NONE);



&#x20;   pb\_assert(pbio\_port\_get\_uart\_dev(self->port, \&self->uart\_dev));

&#x20;   pb\_type\_uart\_device\_set\_baudrate(MP\_OBJ\_FROM\_PTR(self), baudrate\_in);

&#x20;   pbdrv\_uart\_flush(self->uart\_dev);



&#x20;   // Awaitables associated with reading and writing.

&#x20;   self->write\_iter = NULL;

&#x20;   self->read\_iter = NULL;

&#x20;   self->wait\_len = 0;



&#x20;   return MP\_OBJ\_FROM\_PTR(self);

}



static pbio\_error\_t pb\_type\_uart\_device\_write\_iter\_once(pbio\_os\_state\_t \*state, mp\_obj\_t self\_in) {

&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);

&#x20;   GET\_STR\_DATA\_LEN(self->write\_obj, data, data\_len);

&#x20;   return pbdrv\_uart\_write(state, self->uart\_dev, (uint8\_t \*)data, data\_len, self->timeout);

}



static mp\_obj\_t pb\_type\_uart\_device\_write\_return\_map(mp\_obj\_t self\_in) {

&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);

&#x20;   // Write always returns none, but this is effectively a completion callback.

&#x20;   // So we can use it to disconnect the write object so it can be garbage collected.

&#x20;   self->write\_obj = MP\_OBJ\_NULL;

&#x20;   return mp\_const\_none;

}



// pybricks.iodevices.UARTDevice.write

static mp\_obj\_t pb\_type\_uart\_device\_write(size\_t n\_args, const mp\_obj\_t \*pos\_args, mp\_map\_t \*kw\_args) {



&#x20;   PB\_PARSE\_ARGS\_METHOD(n\_args, pos\_args, kw\_args,

&#x20;       pb\_type\_uart\_device\_obj\_t, self,

&#x20;       PB\_ARG\_REQUIRED(data));



&#x20;   // Assert that data argument are bytes

&#x20;   if (!(mp\_obj\_is\_str\_or\_bytes(data\_in) || mp\_obj\_is\_type(data\_in, \&mp\_type\_bytearray))) {

&#x20;       pb\_assert(PBIO\_ERROR\_INVALID\_ARG);

&#x20;   }



&#x20;   // Prevents this object from being garbage collected while the write is in progress.

&#x20;   self->write\_obj = data\_in;



&#x20;   pb\_type\_async\_t config = {

&#x20;       .iter\_once = pb\_type\_uart\_device\_write\_iter\_once,

&#x20;       .parent\_obj = MP\_OBJ\_FROM\_PTR(self),

&#x20;       .return\_map = pb\_type\_uart\_device\_write\_return\_map,

&#x20;   };

&#x20;   return pb\_type\_async\_wait\_or\_await(\&config, \&self->write\_iter, true);

}

static MP\_DEFINE\_CONST\_FUN\_OBJ\_KW(pb\_type\_uart\_device\_write\_obj, 1, pb\_type\_uart\_device\_write);



// pybricks.iodevices.UARTDevice.waiting

static mp\_obj\_t pb\_type\_uart\_device\_waiting(mp\_obj\_t self\_in) {

&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);

&#x20;   return mp\_obj\_new\_int(pbdrv\_uart\_in\_waiting(self->uart\_dev));

}

static MP\_DEFINE\_CONST\_FUN\_OBJ\_1(pb\_type\_uart\_device\_waiting\_obj, pb\_type\_uart\_device\_waiting);



static pbio\_error\_t pb\_type\_uart\_device\_read\_iter\_once(pbio\_os\_state\_t \*state, mp\_obj\_t self\_in) {

&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);

&#x20;   return pbdrv\_uart\_read(state, self->uart\_dev, (uint8\_t \*)self->read\_obj->data, self->read\_obj->len, self->timeout);

}



static mp\_obj\_t pb\_type\_uart\_device\_read\_return\_map(mp\_obj\_t self\_in) {

&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);

&#x20;   mp\_obj\_str\_t \*result = self->read\_obj;

&#x20;   self->read\_obj = NULL;

&#x20;   return pb\_obj\_new\_bytes\_finish(result);

}



// pybricks.iodevices.UARTDevice.read

static mp\_obj\_t pb\_type\_uart\_device\_read(size\_t n\_args, const mp\_obj\_t \*pos\_args, mp\_map\_t \*kw\_args) {



&#x20;   PB\_PARSE\_ARGS\_METHOD(n\_args, pos\_args, kw\_args,

&#x20;       pb\_type\_uart\_device\_obj\_t, self,

&#x20;       PB\_ARG\_DEFAULT\_INT(length, 1));



&#x20;   // Allocate new buffer that we'll read into.

&#x20;   self->read\_obj = pb\_obj\_new\_bytes\_prepare(pb\_obj\_get\_positive\_int(length\_in));



&#x20;   pb\_type\_async\_t config = {

&#x20;       .iter\_once = pb\_type\_uart\_device\_read\_iter\_once,

&#x20;       .parent\_obj = MP\_OBJ\_FROM\_PTR(self),

&#x20;       .return\_map = pb\_type\_uart\_device\_read\_return\_map,

&#x20;   };

&#x20;   return pb\_type\_async\_wait\_or\_await(\&config, \&self->read\_iter, true);

}

static MP\_DEFINE\_CONST\_FUN\_OBJ\_KW(pb\_type\_uart\_device\_read\_obj, 1, pb\_type\_uart\_device\_read);



// pybricks.iodevices.UARTDevice.read\_all

static mp\_obj\_t pb\_type\_uart\_device\_read\_all(mp\_obj\_t self\_in) {



&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);

&#x20;   uint32\_t in\_waiting = pbdrv\_uart\_in\_waiting(self->uart\_dev);



&#x20;   if (in\_waiting == 0) {

&#x20;       return mp\_const\_empty\_bytes;

&#x20;   }



&#x20;   mp\_obj\_str\_t \*result = pb\_obj\_new\_bytes\_prepare(in\_waiting);



&#x20;   // We know we can read this in one go, so all data will be copied without

&#x20;   // intermediate yields.

&#x20;   pbio\_os\_state\_t state = 0;

&#x20;   pb\_assert(pbdrv\_uart\_read(\&state, self->uart\_dev, (uint8\_t \*)result->data, in\_waiting, 0));



&#x20;   return pb\_obj\_new\_bytes\_finish(result);

}

static MP\_DEFINE\_CONST\_FUN\_OBJ\_1(pb\_type\_uart\_device\_read\_all\_obj, pb\_type\_uart\_device\_read\_all);



// pybricks.iodevices.UARTDevice.clear

static mp\_obj\_t pb\_type\_uart\_device\_clear(mp\_obj\_t self\_in) {

&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);

&#x20;   pbdrv\_uart\_flush(self->uart\_dev);

&#x20;   return mp\_const\_none;

}

static MP\_DEFINE\_CONST\_FUN\_OBJ\_1(pb\_type\_uart\_device\_clear\_obj, pb\_type\_uart\_device\_clear);



static pbio\_error\_t pb\_type\_uart\_device\_wait\_until\_iter\_once(pbio\_os\_state\_t \*state, mp\_obj\_t self\_in) {



&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);



retry:



&#x20;   // Yield if not enough to read yet.

&#x20;   if (pbdrv\_uart\_in\_waiting(self->uart\_dev) < self->wait\_len) {

&#x20;       return PBIO\_ERROR\_AGAIN;

&#x20;   }



&#x20;   // We can read the full amount of bytes without blocking now.

&#x20;   for (size\_t i = 0; i < self->wait\_len; i++) {

&#x20;       // Read at most one byte since the viewing window may not overlap pattern.

&#x20;       pbio\_os\_state\_t sub = 0;

&#x20;       uint8\_t rx;

&#x20;       pb\_assert(pbdrv\_uart\_read(\&sub, self->uart\_dev, \&rx, 1, 0));



&#x20;       if (rx != self->wait\_data\[i]) {

&#x20;           // Not the character we expected, so start over, yielding if there

&#x20;           // is not enough to read.

&#x20;           goto retry;

&#x20;       }

&#x20;   }

&#x20;   return PBIO\_SUCCESS;

}



static mp\_obj\_t pb\_type\_uart\_device\_wait\_until\_return\_map(mp\_obj\_t self\_in) {

&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);

&#x20;   self->wait\_len = 0;

&#x20;   self->wait\_data = NULL;

&#x20;   return mp\_const\_none;

}



static mp\_obj\_t pb\_type\_uart\_device\_wait\_until(mp\_obj\_t self\_in, mp\_obj\_t pattern\_in) {



&#x20;   pb\_type\_uart\_device\_obj\_t \*self = MP\_OBJ\_TO\_PTR(self\_in);



&#x20;   if (self->wait\_len) {

&#x20;       pb\_assert(PBIO\_ERROR\_BUSY);

&#x20;   }



&#x20;   self->wait\_data = (const uint8\_t \*)mp\_obj\_str\_get\_data(pattern\_in, \&self->wait\_len);

&#x20;   if (self->wait\_len == 0) {

&#x20;       pb\_assert(PBIO\_ERROR\_INVALID\_ARG);

&#x20;   }



&#x20;   pb\_type\_async\_t config = {

&#x20;       .iter\_once = pb\_type\_uart\_device\_wait\_until\_iter\_once,

&#x20;       .parent\_obj = MP\_OBJ\_FROM\_PTR(self),

&#x20;       .return\_map = pb\_type\_uart\_device\_wait\_until\_return\_map,

&#x20;   };

&#x20;   return pb\_type\_async\_wait\_or\_await(\&config, \&self->read\_iter, true);

}

static MP\_DEFINE\_CONST\_FUN\_OBJ\_2(pb\_type\_uart\_device\_wait\_until\_obj, pb\_type\_uart\_device\_wait\_until);



// dir(pybricks.iodevices.uart\_device)

static const mp\_rom\_map\_elem\_t pb\_type\_uart\_device\_locals\_dict\_table\[] = {

&#x20;   { MP\_ROM\_QSTR(MP\_QSTR\_read),         MP\_ROM\_PTR(\&pb\_type\_uart\_device\_read\_obj)         },

&#x20;   { MP\_ROM\_QSTR(MP\_QSTR\_read\_all),     MP\_ROM\_PTR(\&pb\_type\_uart\_device\_read\_all\_obj)     },

&#x20;   { MP\_ROM\_QSTR(MP\_QSTR\_write),        MP\_ROM\_PTR(\&pb\_type\_uart\_device\_write\_obj)        },

&#x20;   { MP\_ROM\_QSTR(MP\_QSTR\_waiting),      MP\_ROM\_PTR(\&pb\_type\_uart\_device\_waiting\_obj)      },

&#x20;   { MP\_ROM\_QSTR(MP\_QSTR\_wait\_until),   MP\_ROM\_PTR(\&pb\_type\_uart\_device\_wait\_until\_obj)   },

&#x20;   { MP\_ROM\_QSTR(MP\_QSTR\_set\_baudrate), MP\_ROM\_PTR(\&pb\_type\_uart\_device\_set\_baudrate\_obj) },

&#x20;   { MP\_ROM\_QSTR(MP\_QSTR\_clear),        MP\_ROM\_PTR(\&pb\_type\_uart\_device\_clear\_obj)        },

};

static MP\_DEFINE\_CONST\_DICT(pb\_type\_uart\_device\_locals\_dict, pb\_type\_uart\_device\_locals\_dict\_table);



// type(pybricks.iodevices.uart\_device)

MP\_DEFINE\_CONST\_OBJ\_TYPE(pb\_type\_uart\_device,

&#x20;   MP\_QSTR\_uart\_device,

&#x20;   MP\_TYPE\_FLAG\_NONE,

&#x20;   make\_new, pb\_type\_uart\_device\_make\_new,

&#x20;   locals\_dict, \&pb\_type\_uart\_device\_locals\_dict);



\#endif // PYBRICKS\_PY\_IODEVICES



```



</details>



