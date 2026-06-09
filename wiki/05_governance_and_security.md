# Gobernanza y Seguridad en Sistemas de Agentes

Cuando un agente deja de ser un simple chatbot de consulta y se le otorga la capacidad de tomar acciones en el mundo real (e.g., escribir en bases de datos, enviar correos, invocar APIs externas de pago), el riesgo de seguridad se eleva exponencialmente. Los ataques de **Prompt Injection** (inyección de prompts) o **Jailbreaks** (saltarse las restricciones del sistema) hacen que delegar la seguridad únicamente a las "instrucciones del sistema" sea un grave error de ingeniería.

En esta guía analizaremos el diseño de una capa de **Gobernanza a Nivel de Runtime** utilizando el patrón Wrapper, el control de acceso basado en roles (RBAC) para herramientas, el filtrado automático de información confidencial (PII), los controles financieros y de tasa (*rate limiters*) y los interruptores de emergencia (*kill switches*).

Vínculo al código de referencia: [05_governance_and_security.py](../00_primitives_scratch/05_governance_and_security.py)

---

## 🛡️ Seguridad de Sistemas vs. Seguridad de Prompts

El principio fundamental de la seguridad en ingeniería de IA es:

> [!IMPORTANT]
> **La seguridad de un agente es un problema de ingeniería de sistemas, no un truco de redacción de prompts.**
>
> Nunca asumas que un modelo respetará la instrucción *"No llames a la herramienta X si el usuario no es administrador"*. Un atacante experto puede redactar un prompt persuasivo que anule las directrices del sistema (Jailbreaking). La validación de seguridad debe realizarse de forma obligatoria en la capa de software (Python/Runtime) que envuelve el acceso a las herramientas.

```
                  ┌───────────────────────────────┐
                  │        USUARIO ATACANTE       │
                  └───────────────┬───────────────┘
                                  │ (Prompt Injection / Jailbreak)
                                  ▼
                  ┌───────────────────────────────┐
                  │      MODELO DE LENGUAJE       │
                  │  (Decide llamar a Tool Admin) │
                  └───────────────┬───────────────┘
                                  │ (Intento de llamada)
                                  ▼
                  ┌───────────────────────────────┐
                  │       RUNTIME GATEWAY         │
                  │   [ GATER RULE INSPECTION ]   │
                  └───────────────┬───────────────┘
                     Lacks Perms? │ (Blocks Execution)
                                  ▼
                  ┌───────────────────────────────┐
                  │        BLOCKED / ERROR        │
                  │ (La herramienta nunca se abre)│
                  └───────────────────────────────┘
```

---

## 🔒 Patrón Wrapper: El Interceptor de Ejecución (ToolGater)

Para proteger nuestras herramientas de ejecuciones no autorizadas, implementamos la clase `ToolGater` en [05_governance_and_security.py](../00_primitives_scratch/05_governance_and_security.py#L76-L127). Este diseño está inspirado en la arquitectura del **Agent Governance Toolkit de Microsoft**.

En lugar de exponer la función cruda de la herramienta al agente, la envolvemos en un decorador protector que intercepta los parámetros y valida múltiples capas de políticas de seguridad antes de autorizar la ejecución física de la función:

```python
class ToolGater:
    def __init__(self, state: SystemState, policy: GovernancePolicy):
        self.state = state
        self.policy = policy

    def govern(self, agent_role: str, tool_name: str, fn: Callable[[str], str]) -> Callable[[str], str]:
        def protected_tool(args: str) -> str:
            # 1. Validación de Interruptor de Emergencia (Kill Switch)
            # 2. Validación de Roles y Permisos (RBAC)
            # 3. Control de Presupuesto Acumulativo (Budget Gate)
            # 4. Control de Tasa (Rate Limit)
            # 5. Redacción de Privacidad (PII Masking)
            
            # Si todo pasa, se ejecuta la función real
            return fn(clean_args)
        return protected_tool
```

---

## 🧩 Implementación de Políticas de Seguridad

Analicemos en detalle cada regla de gobernanza implementada a bajo nivel:

### 1. Control de Acceso Basado en Roles (RBAC)
Asocia herramientas específicas con roles mínimos autorizados. Si un agente configurado con el rol de `"viewer"` intenta invocar una herramienta restrictiva como `"create_system_user"`, el runtime bloquea la llamada levantando un error de permisos inmediatamente, evitando que el intento llegue al backend:

```python
if agent_role not in self.policy.allowed_roles:
    raise PermissionError(f"Block: Role '{agent_role}' lacks permissions for tool '{tool_name}'.")
```

### 2. Filtrado y Enmascaramiento de PII
Los LLMs en la nube procesan datos en servidores externos. Para cumplir con regulaciones de privacidad de datos (e.g., GDPR), el gater escanea los argumentos de entrada en busca de información personal identificable (PII) como correos electrónicos y números de teléfono utilizando expresiones regulares robustas antes de realizar la llamada:

```python
email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
masked = re.sub(email_pattern, "[REDACTED_EMAIL]", text)
```

### 3. Presupuesto Acumulativo Financiero (Budget Gate)
Los agentes autónomos que se ejecutan en bucles infinitos por errores lógicos consumen tokens a gran velocidad. El estado del sistema (`SystemState`) lleva un registro acumulado del costo de cada llamada. Si el costo supera un límite diario parametrizado (e.g., $\$1.00$ USD), el `ToolGater` detiene todas las llamadas subsiguientes de forma automatizada:

```python
if not self.state.check_budget():
    raise BudgetError("Block: Operation budget exceeded!")
```

### 4. Control de Tasa mediante Ventana Deslizable (Rate Limiting)
Para proteger las APIs externas y evitar denegaciones de servicio (DoS) accidentales, el gater mantiene una cola de marcas de tiempo (*timestamps*) dentro del último minuto. Si el volumen de llamadas de herramientas supera el umbral (e.g., 5 llamadas por minuto), se aplica un estrangulamiento (*throttling*):

```python
def throttle_check(self, limit_per_minute: int = 5) -> bool:
    now = time.time()
    # Limpiar timestamps antiguos
    self.tool_call_timestamps = [t for t in self.tool_call_timestamps if now - t < 60]
    if len(self.tool_call_timestamps) >= limit_per_minute:
        return False
    self.tool_call_timestamps.append(now)
    return True
```

### 5. Interruptor de Emergencia (Kill Switch)
En caso de detectar comportamientos anómalos o sospechosos en producción, los operadores del sistema pueden activar un interruptor global de emergencia (`kill_switch_engaged = True`). Al activarse, se cancela la ejecución de cualquier herramienta de forma inmediata, permitiendo a los ingenieros aislar el entorno antes de sufrir pérdidas de datos o financieras.
