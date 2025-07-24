Set-Location -Path "$PSScriptRoot"

$backend = "."

# Elimina base de datos SQLite
if (Test-Path "$backend\db.sqlite3") {
    Remove-Item "$backend\db.sqlite3" -Force
    Write-Host "✅ Base de datos 'db.sqlite3' eliminada."
}

# Eliminar archivos de migración excepto __init__.py
Get-ChildItem -Path $backend -Recurse -Include *.py -Exclude __init__.py | Where-Object {
    $_.DirectoryName -like "*\migrations*"
} | Remove-Item -Force

Write-Host "🧹 Migraciones eliminadas."

# Ejecutar makemigrations y migrate
Set-Location -Path $backend
Write-Host "⚙️  Ejecutando makemigrations..."
python manage.py makemigrations

Write-Host "⚙️  Ejecutando migrate..."
python manage.py migrate

# Crear superusuario automáticamente si no existe
Write-Host "👤 Verificando superusuario..."
$create_superuser_script = @"
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
"@
$create_superuser_script | python manage.py shell

Write-Host "`n✅ Todo listo. Migraciones, base de datos y superusuario creados correctamente."
