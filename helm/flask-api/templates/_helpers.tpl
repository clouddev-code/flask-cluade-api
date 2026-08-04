{{- define "flask-api.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "flask-api.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "flask-api.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "flask-api.labels" -}}
app.kubernetes.io/name: {{ include "flask-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "flask-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "flask-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "flask-api.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "flask-api.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
