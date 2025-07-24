from rest_framework import serializers
from .models import Accion, Cartera, PrecioHistorico

class AccionSerializer(serializers.ModelSerializer):
    ganancia = serializers.SerializerMethodField()
    rentabilidad_pct = serializers.SerializerMethodField()

    class Meta:
        model = Accion
        fields = ['id', 'nombre', 'ticker', 'cantidad', 'precio_compra', 'precio_actual', 'ganancia', 'rentabilidad_pct']

    def get_ganancia(self, obj):
        return (obj.precio_actual - obj.precio_compra) * obj.cantidad

    def get_rentabilidad_pct(self, obj):
        return ((obj.precio_actual - obj.precio_compra) / obj.precio_compra) * 100

class PrecioHistoricoSerializer(serializers.ModelSerializer):
    ticker = serializers.CharField(source="accion.ticker", read_only=True)

    class Meta:
        model = PrecioHistorico
        fields = ["ticker", "fecha", "precio_cierre"]

class CarteraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cartera
        fields = ['id', 'usuario', 'nombre']
