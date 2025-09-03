
@echo off
set ARG=%1



if "%ARG%"=="1" (
    echo Eseguo proto_vio_main.py
    streamlit run proto_vio_main.py
    goto end
)
if "%ARG%"=="2" (
    echo Eseguo proto_vio_ ... .py
    streamlit run proto_vio_ ... .py
    goto end
)

echo ❌ Errore: parametro non valido. Usa 1, 2 o 3.
echo Esempio: webmatch.bat 1

:end

pause
