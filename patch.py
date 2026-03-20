import sys
path = r'c:\Users\amana\Desktop\hr-system\frontend\hr-dashboard\src\pages\DatabasePage.tsx'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace("import { candidatesApi, applicationsApi, clientsApi, monitoringApi } from '@/lib/api';", "import { candidatesApi, applicationsApi, clientsApi, monitoringApi, jobsApi } from '@/lib/api';")

old_promise = '''      const [candidatesRes, applicationsRes, clientsList, dbSourceRes] = await Promise.allSettled([
        candidatesApi.list({}, 1, 100),
        applicationsApi.list({}, 1, 100),
        clientsApi.list(),
        monitoringApi.getDatabaseSource(),
      ]);'''
new_promise = '''      const [candidatesRes, applicationsRes, clientsList, jobsRes, dbSourceRes] = await Promise.allSettled([
        candidatesApi.list({}, 1, 100),
        applicationsApi.list({}, 1, 100),
        clientsApi.list(),
        jobsApi.list({}, 1, 100),
        monitoringApi.getDatabaseSource(),
      ]);'''
text = text.replace(old_promise, new_promise)

old_jobs = '''      // Jobs & Interviews — no backend endpoint yet
      data.jobs = {
        columns: ['ID', 'Title', 'Client ID', 'Status', 'Openings', 'Created At'],
        rows: [],
      };'''
new_jobs = '''      // Jobs
      if (jobsRes.status === 'fulfilled') {
        const jobs = jobsRes.value.data;
        data.jobs = {
          columns: ['ID', 'Title', 'Company / Client', 'Experience', 'Salary (LPA)', 'Location', 'Created At'],
          rows: jobs.map(j => [
            j.id,
            j.title,
            j.companyName || j.clientId || '-',
            j.experienceRequired !== undefined ? \\ yrs\ : '-',
            j.salaryLpa !== undefined ? j.salaryLpa.toString() : '-',
            j.location || '-',
            j.createdAt ? new Date(j.createdAt).toLocaleDateString() : '-',
          ]),
        };
      } else {
        data.jobs = { columns: ['Error'], rows: [['Failed to load jobs: ' + jobsRes.reason]] };
      }

      // Interviews — no backend endpoint yet'''
text = text.replace(old_jobs, new_jobs)

old_export_button = '''            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>'''
new_export_button = '''            <Button variant="outline" size="sm" onClick={handleExport}>
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>'''
text = text.replace(old_export_button, new_export_button)

export_func = '''  const handleExport = useCallback(() => {
    if (!currentTable || currentTable.columns.length === 0 || filteredRows.length === 0) return;
    const header = currentTable.columns.join(',');
    const csvRows = filteredRows.map(row => 
      row.map(cell => \"\\"\).join(',')
    );
    const csvString = [header, ...csvRows].join('\\n');
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', \\\_Export_\\.csv\);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [currentTable, filteredRows, tableName]);

  return ('''
text = text.replace('  return (', export_func)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Patched successfully")
