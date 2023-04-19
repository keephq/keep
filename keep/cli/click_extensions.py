import click


class NotRequiredIf(click.Option):
    """
    https://stackoverflow.com/questions/44247099/click-command-line-interfaces-make-options-required-if-other-optional-option-is
    """

    def __init__(self, *args, **kwargs):
        self.not_required_if = kwargs.pop("not_required_if")
        assert self.not_required_if, "'not_required_if' parameter required"
        kwargs["help"] = (
            kwargs.get("help", "")
            + f" NOTE: This argument is mutually exclusive with {self.not_required_if}"
        ).strip()
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        we_are_present = self.name in opts
        other_present = self.not_required_if in opts

        if other_present is False:
            if we_are_present is False:
                raise click.UsageError(
                    "Illegal usage: `%s` is required when `%s` is not provided"
                    % (self.name, self.not_required_if)
                )
            else:
                self.prompt = None

        return super().handle_parse_result(ctx, opts, args)
