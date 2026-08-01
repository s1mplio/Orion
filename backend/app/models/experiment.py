class Experiment:

    def __init__(
        self,
        title,
        objective,
        methodology,
        required_data,
        expected_outcomes,
        evaluation_metrics,
        limitations
    ):

        self.title = title
        self.objective = objective
        self.methodology = methodology
        self.required_data = required_data
        self.expected_outcomes = expected_outcomes
        self.evaluation_metrics = evaluation_metrics
        self.limitations = limitations