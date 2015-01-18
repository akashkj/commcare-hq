import functools
import json
from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.conditional import ConditionalExpression
from corehq.apps.userreports.expressions.context_specific import BaseDocExpression
from corehq.apps.userreports.expressions.specs import PropertyNameGetterSpec, PropertyPathGetterSpec, \
    ConditionalExpressionSpec, ConstantGetterSpec, BaseDocExpressionSpec


def _simple_expression_generator(wrapper_class, spec, context):
    return wrapper_class.wrap(spec).expression

_constant_expression = functools.partial(_simple_expression_generator, ConstantGetterSpec)
_property_name_expression = functools.partial(_simple_expression_generator, PropertyNameGetterSpec)
_property_path_expression = functools.partial(_simple_expression_generator, PropertyPathGetterSpec)

def _conditional_expression(spec, context):
    # no way around this since the two factories inherently depend on each other
    from corehq.apps.userreports.filters.factory import FilterFactory
    wrapped = ConditionalExpressionSpec.wrap(spec)
    return ConditionalExpression(
        FilterFactory.from_spec(wrapped.test, context),
        ExpressionFactory.from_spec(wrapped.expression_if_true, context),
        ExpressionFactory.from_spec(wrapped.expression_if_false, context),
    )


def _base_doc_expression(spec, context):
    wrapped = BaseDocExpressionSpec.wrap(spec)
    return BaseDocExpression(
        expression=ExpressionFactory.from_spec(wrapped.expression, context)
    )


class ExpressionFactory(object):
    spec_map = {
        'constant': _constant_expression,
        'property_name': _property_name_expression,
        'property_path': _property_path_expression,
        'conditional': _conditional_expression,
        'base_doc': _base_doc_expression,
    }

    @classmethod
    def from_spec(cls, spec, context=None):
        try:
            return cls.spec_map[spec['type']](spec, context)
        except KeyError:
            raise BadSpecError(_('Invalid getter type: {}. Valid options are: {}').format(
                spec['type'],
                ', '.join(cls.spec_map.keys()),
            ))
        except BadValueError as e:
            raise BadSpecError(_('Problem creating getter: {}. Message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))
