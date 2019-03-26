/* globals hqDefine */
hqDefine('userreports/js/data_source_evaluator', function () {
    var dataSourceModel = function (submitUrl) {
        var self = {};
        self.submitUrl = submitUrl;
        self.documentsId = ko.observable();
        self.dataSourceId = ko.observable();
        self.uiFeedback = ko.observable();
        self.columns = ko.observable();
        self.rows = ko.observableArray();
        self.dbRows = ko.observableArray();
        self.loading = ko.observable(false);

        self.evaluateDataSource = function () {
            self.uiFeedback("");
            if (!self.documentsId()) {
                self.uiFeedback("Please enter a document ID.");
            }
            else {
                self.loading(true);
                $.post({
                    url: self.submitUrl,
                    data: {
                        docs_id: self.documentsId(),
                        data_source: self.dataSourceId(),
                    },
                    success: function (data) {
                        function transform_rows(rows) {
                            var output = [];
                            rows.forEach(function (row) {
                                var tableRow = [];
                                data.columns.forEach(function (column) {
                                    tableRow.push(row[column]);
                                });
                                output.push(tableRow);
                            });
                            return output;
                        }

                        self.rows(transform_rows(data.rows));
                        self.dbRows(transform_rows(data.db_rows));
                        self.columns(data.columns);
                        self.loading(false);
                    },
                    error: function (data) {
                        self.loading(false);
                        self.uiFeedback("<strong>Failure!:</strong> " + data.responseJSON.error);
                    },
                });
            }
        };

        return self;
    };

    $(function () {
        var submitUrl = hqImport("hqwebapp/js/initial_page_data").reverse("data_source_evaluator");
        ko.applyBindings(
            dataSourceModel(submitUrl),
            document.getElementById('data-source-debugger')
        );
    });
});
