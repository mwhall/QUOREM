from django.db.models.expressions import F, Value as BaseValue, Func, Expression

class V(BaseValue):
    def as_sql(self, compiler, connection):
        if self._output_field_or_none and (self._output_field_or_none.get_internal_type() == 'ArrayField'):
            base_field = self._output_field_or_none.base_field
            return '%s::%s[]' % ('%s', base_field.db_type(connection)), [self.value]
        return super(V, self).as_sql(compiler, connection)

class SimpleFunc(Func):
    def __init__(self, field, *values, **extra):
        if not isinstance(field, Expression):
            field  = F(field)
            if values and not isinstance(values[0], Expression):
                values = [V(v) for v in values]
        super(SimpleFunc, self).__init__(field, *values, **extra)
        
class ArrayPosition(SimpleFunc):
    function = 'ARRAY_POSITION'
        
class ArrayPositions(SimpleFunc):
    function = 'ARRAY_POSITIONS'
    
class Unnest(Func):
    function = 'UNNEST'
