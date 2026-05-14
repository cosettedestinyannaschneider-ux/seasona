from sqlalchemy import Enum as SAEnum


def enum_column(enum_cls):
    return SAEnum(
        enum_cls,
        values_callable=lambda enum: [member.value for member in enum],
        name=f"{enum_cls.__name__.lower()}_enum",
    )

