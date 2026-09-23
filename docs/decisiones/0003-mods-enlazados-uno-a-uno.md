# 0003 — `mods/` se enlaza jar a jar, no como carpeta

**Fecha:** 2026-09-22 · **Estado:** aceptada

## Contexto

El directorio de trabajo de cada semilla no debe copiar los 1,4 GB de `mods/`, así que la primera
versión enlazaba la carpeta entera con un symlink.

## Síntoma

El servidor moría en el arranque, antes de cargar ningún mod:

```
Exception in thread "main" org.spongepowered.asm.launch.MixinInitialisationError:
  Error initialising mixin config jasione.mixins.json
Caused by: java.lang.IllegalArgumentException:
  The specified resource 'jasione.mixins.json' was invalid or could not be read
```

## Causa

`jasione` (mod de optimización de `Enum#values`) se carga como `ITransformationService` en el
arranque de ModLauncher. Su `MANIFEST.MF` declara `MixinConfigs: jasione.mixins.json`, pero ese
archivo no está suelto en el jar: está dentro de `jasione-forge-mod.jar`, anidado en la raíz.
Con la carpeta enlazada, ModLauncher no llega a resolver ese jar anidado. En la instalación base,
con `mods/` real, el mismo mod carga sin problema.

## Decisión

`mods/` se crea como directorio de verdad y dentro va un symlink por jar, apuntando a la ruta
resuelta del original. Sigue sin copiarse nada y la instalación base sigue intacta.

## Consecuencias

- Son 339 symlinks por semilla: instantáneo y sin coste de disco.
- Si aparece otro mod que se cargue como servicio y tampoco resuelva su jar anidado, el siguiente
  paso sería copiar ese jar concreto, no toda la carpeta.
