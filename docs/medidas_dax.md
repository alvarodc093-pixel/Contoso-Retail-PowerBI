# Medidas DAX

Generado por `generar_pbip.py` a partir de `modelo.py`. Todas las medidas están en la tabla `ventas`.

## 1. Ventas

### Ventas

Importe vendido en USD, con descuentos (cantidad x precio neto).

```dax
Ventas =
SUMX ( ventas, ventas[cantidad] * ventas[precio_neto] )
```

### Coste

Coste de los productos vendidos en USD.

```dax
Coste =
SUMX ( ventas, ventas[cantidad] * ventas[coste_unitario] )
```

### Margen

Ventas menos coste.

```dax
Margen =
[Ventas] - [Coste]
```

### Margen %

Margen bruto sobre ventas.

```dax
Margen % =
DIVIDE ( [Margen], [Ventas] )
```

### Unidades

Unidades vendidas.

```dax
Unidades =
SUM ( ventas[cantidad] )
```

### Pedidos

Número de pedidos distintos (un pedido tiene varias líneas).

```dax
Pedidos =
DISTINCTCOUNT ( ventas[pedido_id] )
```

### Ticket medio

Importe medio por pedido.

```dax
Ticket medio =
DIVIDE ( [Ventas], [Pedidos] )
```

### Descuento medio %

Cuánto se rebaja de media el precio de tarifa.

```dax
Descuento medio % =
VAR tarifa = SUMX ( ventas, ventas[cantidad] * ventas[precio_unitario] )
RETURN
    IF ( NOT ISBLANK ( tarifa ), 1 - DIVIDE ( [Ventas], tarifa ) )
```

## 2. Clientes

### Clientes

Clientes distintos que compran en el periodo.

```dax
Clientes =
DISTINCTCOUNT ( ventas[cliente_id] )
```

### Clientes nuevos

Clientes cuya primera compra cae dentro del periodo.

```dax
Clientes nuevos =
VAR inicio = MIN ( calendario[fecha] )
VAR fin = MAX ( calendario[fecha] )
VAR primeras =
    ADDCOLUMNS (
        VALUES ( ventas[cliente_id] ),
        "@primera", CALCULATE ( MIN ( ventas[fecha] ), REMOVEFILTERS ( calendario ) )
    )
RETURN
    COUNTROWS ( FILTER ( primeras, [@primera] >= inicio && [@primera] <= fin ) )
```

### % clientes nuevos

Parte de los clientes del periodo que compran por primera vez.

```dax
% clientes nuevos =
DIVIDE ( [Clientes nuevos], [Clientes] )
```

## 3. Tiempo

### Ventas AA

Ventas del mismo periodo del año anterior.

```dax
Ventas AA =
CALCULATE ( [Ventas], SAMEPERIODLASTYEAR ( calendario[fecha] ) )
```

### Var vs AA

Diferencia frente al año anterior.

```dax
Var vs AA =
IF ( NOT ISBLANK ( [Ventas AA] ), [Ventas] - [Ventas AA] )
```

### Var vs AA %

Crecimiento frente al año anterior.

```dax
Var vs AA % =
DIVIDE ( [Var vs AA], [Ventas AA] )
```

### Ventas acumuladas año

Ventas desde el 1 de enero hasta la fecha del contexto.

```dax
Ventas acumuladas año =
TOTALYTD ( [Ventas], calendario[fecha] )
```

### Ventas acumuladas año AA

Lo mismo, un año antes.

```dax
Ventas acumuladas año AA =
CALCULATE ( [Ventas acumuladas año], SAMEPERIODLASTYEAR ( calendario[fecha] ) )
```

### Ventas media móvil 3M

Media mensual de los últimos 3 meses.

```dax
Ventas media móvil 3M =
VAR fin = MAX ( calendario[fecha] )
RETURN
    DIVIDE (
        CALCULATE ( [Ventas], DATESINPERIOD ( calendario[fecha], fin, -3, MONTH ) ),
        3
    )
```

### Margen % AA

Margen % del año anterior.

```dax
Margen % AA =
CALCULATE ( [Margen %], SAMEPERIODLASTYEAR ( calendario[fecha] ) )
```

## 4. Canales

### Ventas online

Ventas de la tienda online.

```dax
Ventas online =
CALCULATE ( [Ventas], tiendas[canal] = "Online" )
```

### % online

Peso de la tienda online en las ventas.

```dax
% online =
DIVIDE ( [Ventas online], [Ventas] )
```

### Ventas tiendas físicas

Ventas de las tiendas físicas.

```dax
Ventas tiendas físicas =
CALCULATE ( [Ventas], tiendas[canal] = "Tienda física" )
```

### Ventas por m²

Ventas de tienda física entre los m² de las tiendas que han vendido en el periodo.

```dax
Ventas por m² =
VAR tiendasConVentas =
    FILTER ( VALUES ( tiendas[tienda_id] ), [Ventas tiendas físicas] > 0 )
VAR superficie =
    SUMX ( tiendasConVentas, CALCULATE ( SUM ( tiendas[m2] ) ) )
RETURN
    DIVIDE ( [Ventas tiendas físicas], superficie )
```

## 1. Ventas

### Ranking categoría

Puesto de la categoría por ventas dentro de la selección.

```dax
Ranking categoría =
IF (
    HASONEVALUE ( categorias[categoria] ),
    RANKX ( ALLSELECTED ( categorias[categoria] ), [Ventas] )
)
```

## 5. Objetivos

### Objetivo

Presupuesto de ventas: mismo mes del año anterior + 8 %.

```dax
Objetivo =
SUM ( objetivos[objetivo] )
```

### Desviación vs objetivo

Ventas menos objetivo.

```dax
Desviación vs objetivo =
IF ( NOT ISBLANK ( [Objetivo] ), [Ventas] - [Objetivo] )
```

### Cumplimiento %

Ventas sobre objetivo (100 % = objetivo cumplido).

```dax
Cumplimiento % =
DIVIDE ( [Ventas], [Objetivo] )
```

### Objetivo acumulado año

Objetivo desde el 1 de enero.

```dax
Objetivo acumulado año =
TOTALYTD ( [Objetivo], calendario[fecha] )
```

### Estado objetivo

Semáforo de cumplimiento en texto.

```dax
Estado objetivo =
VAR c = [Cumplimiento %]
RETURN
    SWITCH (
        TRUE (),
        ISBLANK ( c ), BLANK (),
        c >= 1, "Cumplido",
        c >= 0.9, "Cerca (90-100 %)",
        "Por debajo del 90 %"
    )
```
