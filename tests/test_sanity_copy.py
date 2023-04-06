def alert_test():
    runner = CliRunner()
    for alert in os.listdir("examples/alerts"):
        log_output_buffer = io.StringIO()
        handler = logging.StreamHandler(log_output_buffer)
        handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(handler)
        alert_path = os.path.join("examples/alerts", alert)
        result = runner.invoke(run, ["--alerts-file", alert_path])
        log_contents = log_output_buffer.getvalue()
        assert result.exit_code == 0
        for line in log_contents.splitlines():
            assert "error" not in line.lower()
