# Agent Skills (skills.sh)

Para mejorar el comportamiento de agentes (Cursor, Claude, etc.) al trabajar con este proyecto, puedes instalar skills desde [skills.sh](https://skills.sh/).

## Instalación

Desde la raíz del proyecto (o desde cualquier directorio donde quieras que se registren los skills):

```bash
npx skills add vercel-labs/agent-browser
npx skills add anthropics/pdf
npx skills add browser-use/browser-use
npx skills add anthropics/webapp-testing
```

## Skills recomendados

| Skill | Uso |
|-------|-----|
| `vercel-labs/agent-browser` | Automatización de navegador robusta |
| `anthropics/pdf` | Generación de reportes en PDF |
| `browser-use/browser-use` | Browser automation avanzada |
| `anthropics/webapp-testing` | Testing de interacciones web |

## Listar skills instalados

```bash
npx skills list
```

Estos skills mejoran la capacidad del agente para depurar el scraper, generar reportes en PDF y probar flujos en el portal.
