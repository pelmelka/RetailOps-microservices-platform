{{- define "mwp.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mwp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "mwp.labels" -}}
helm.sh/chart: {{ include "mwp.chart" . }}
app.kubernetes.io/name: {{ include "mwp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "mwp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mwp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "mwp.componentLabels" -}}
{{- include "mwp.labels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "mwp.componentSelectorLabels" -}}
{{- include "mwp.selectorLabels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "mwp.image" -}}
{{- $root := .root -}}
{{- $image := .image -}}
{{- $registry := default $root.Values.global.imageRegistry $image.registry -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $image.repository $image.tag -}}
{{- else -}}
{{- printf "%s:%s" $image.repository $image.tag -}}
{{- end -}}
{{- end -}}

{{- define "mwp.imagePullPolicy" -}}
{{- $root := .root -}}
{{- $image := .image -}}
{{- default $root.Values.global.imagePullPolicy $image.pullPolicy -}}
{{- end -}}

{{- define "mwp.externalImage" -}}
{{- $image := . -}}
{{- $registry := default "" $image.registry -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $image.repository $image.tag -}}
{{- else -}}
{{- printf "%s:%s" $image.repository $image.tag -}}
{{- end -}}
{{- end -}}

{{- define "mwp.databaseUrl" -}}
{{- if .Values.appSecrets.databaseUrl -}}
{{- .Values.appSecrets.databaseUrl -}}
{{- else -}}
{{- printf "postgresql+asyncpg://%s:%s@postgres:%v/%s" .Values.postgres.auth.username .Values.postgres.auth.password .Values.postgres.servicePort .Values.postgres.auth.database -}}
{{- end -}}
{{- end -}}

{{- define "mwp.backendResources" -}}
{{- $resources := .resources -}}
{{- if $resources -}}
{{- toYaml $resources -}}
{{- else -}}
{{- toYaml .root.Values.resources.default -}}
{{- end -}}
{{- end -}}
