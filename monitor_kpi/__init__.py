"""Sistema de monitoreo diario de KPIs con detección de desviaciones.

Compara cada día contra el día anterior disponible y genera alertas
LEVE o GRAVE cuando un KPI se deteriora más allá de los umbrales
configurados en :mod:`monitor_kpi.config`.
"""

__version__ = "1.0.0"
