"""
ReportLab PDF generator that overlays duty log data onto the RODs_Ex.pdf template.

Uses PyPDF2 to read the template and ReportLab canvas to draw overlay text/graphics,
then merges them into a final PDF that visually matches the original template.
"""

import io
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import black, Color
from reportlab.pdfgen import canvas

from PyPDF2 import PdfReader, PdfWriter


class RODSPDFGenerator:
    """Generates RODS (Record of Duty Status) PDFs by overlaying data onto the template."""

    # Colors for duty status lines on the grid (high contrast for visibility)
    STATUS_COLORS = {
        'off_duty': Color(0.3, 0.3, 0.3),            # Dark gray
        'sleeper_berth': Color(0.0, 0.2, 0.7),        # Dark blue
        'driving': Color(0.0, 0.5, 0.0),              # Dark green
        'on_duty_not_driving': Color(0.8, 0.4, 0.0),  # Dark orange
    }

    def __init__(self, template_path: str = None, mapping_path: str = None):
        from django.conf import settings
        self.template_path = template_path or str(settings.RODS_TEMPLATE_PATH)
        mapping_file = mapping_path or str(settings.ELD_MAPPING_PATH)

        with open(mapping_file, 'r') as f:
            self.mapping = json.load(f)

        self.grid = self.mapping['graph_grid']
        self.fields = self.mapping['fields']


    def _time_to_x(self, dt: datetime, is_end=False) -> float:
        """Convert a datetime's time-of-day to an x coordinate on the 24-hour grid.
        If is_end=True and the time is exactly midnight, treat as end-of-day (hour 24)."""
        hours = dt.hour + dt.minute / 60.0
        if is_end and hours == 0.0:
            hours = 24.0
        grid_left = self.grid['left_x']
        hour_width = self.grid['hour_width']
        return grid_left + hours * hour_width

    def _status_to_y(self, status: str) -> float:
        """Get the y coordinate for a duty status row."""
        return self.grid['rows'][status]['y']

    def _draw_text(self, c: canvas.Canvas, field_key: str, text: str):
        """Draw text at a mapped field position."""
        if field_key not in self.fields:
            return
        field = self.fields[field_key]
        c.setFont(field.get('font', 'Helvetica'), field.get('size', 10))
        x, y = field['x'], field['y']
        align = field.get('align', 'left')

        if align == 'center':
            c.drawCentredString(x, y, str(text))
        elif align == 'right':
            c.drawRightString(x, y, str(text))
        else:
            c.drawString(x, y, str(text))

    def _draw_header_fields(
        self,
        c: canvas.Canvas,
        log_date: date,
        from_location: str,
        to_location: str,
        carrier_name: str,
        main_office_address: str,
        home_terminal_address: str,
        total_miles_driving: float,
        total_mileage: float,
        vehicle_numbers: str,
        shipping_doc: str = "",
        shipper_commodity: str = "",
    ):
        """Draw all header/footer text fields onto the overlay."""
        self._draw_text(c, 'date_month', str(log_date.month).zfill(2))
        self._draw_text(c, 'date_day', str(log_date.day).zfill(2))
        self._draw_text(c, 'date_year', str(log_date.year))
        self._draw_text(c, 'from_location', from_location)
        self._draw_text(c, 'to_location', to_location)
        self._draw_text(c, 'carrier_name', carrier_name)
        self._draw_text(c, 'main_office_address', main_office_address)
        self._draw_text(c, 'home_terminal_address', home_terminal_address)
        self._draw_text(c, 'total_miles_driving', f"{total_miles_driving:.0f}")
        self._draw_text(c, 'total_mileage_today', f"{total_mileage:.0f}")
        self._draw_text(c, 'vehicle_numbers', vehicle_numbers)

        if shipping_doc:
            self._draw_text(c, 'shipping_doc', shipping_doc)
        if shipper_commodity:
            self._draw_text(c, 'shipper_commodity', shipper_commodity)

    def _draw_graph_grid(self, c: canvas.Canvas, entries: list[dict]):
        """
        Draw duty status lines on the 24-hour grid.

        Each entry is a dict with: status, start_time (datetime), end_time (datetime).
        Draws horizontal lines for each duty period and vertical transition lines.
        """
        line_width = self.grid.get('line_width', 3.0)
        c.setLineWidth(line_width)
        c.setLineCap(1)  # Round cap for smoother lines

        # Sort entries by start_time
        sorted_entries = sorted(entries, key=lambda e: e['start_time'] if not isinstance(e['start_time'], str) else datetime.fromisoformat(e['start_time']))

        prev_entry = None

        for entry in sorted_entries:
            status = entry['status']
            start_time = entry['start_time']
            end_time = entry.get('end_time') or start_time

            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)

            start_x = self._time_to_x(start_time)
            end_x = self._time_to_x(end_time, is_end=True)

            # Skip zero-width entries
            if abs(end_x - start_x) < 0.5:
                continue

            row_y = self._status_to_y(status)

            # Set color for this status
            color = self.STATUS_COLORS.get(status, black)
            c.setStrokeColor(color)

            # Draw horizontal line for this status period
            c.line(start_x, row_y, end_x, row_y)

            # Draw vertical transition line from previous status
            if prev_entry:
                prev_status = prev_entry['status'] if isinstance(prev_entry['status'], str) else prev_entry['status']
                prev_y = self._status_to_y(prev_status)
                if prev_y != row_y:
                    c.setStrokeColor(black)
                    c.setLineWidth(1.5)
                    c.line(start_x, prev_y, start_x, row_y)
                    c.setLineWidth(line_width)

            prev_entry = entry

    def _draw_total_hours(
        self,
        c: canvas.Canvas,
        off_duty_hours: float,
        sleeper_hours: float,
        driving_hours: float,
        on_duty_hours: float,
    ):
        """Draw total hours for each duty status in the right column."""
        totals_config = self.mapping.get('total_hours_column', {})
        x = totals_config.get('x', 740)
        font = totals_config.get('font', 'Helvetica')
        size = totals_config.get('size', 9)

        c.setFont(font, size)
        c.setFillColor(black)

        rows = totals_config.get('rows', {})
        values = {
            'off_duty': off_duty_hours,
            'sleeper_berth': sleeper_hours,
            'driving': driving_hours,
            'on_duty_not_driving': on_duty_hours,
        }

        for status, hours in values.items():
            if status in rows:
                y = rows[status]['y']
                c.drawCentredString(x, y, f"{hours:.1f}")

    def _draw_remarks(self, c: canvas.Canvas, remarks: list[str]):
        """Draw remarks (location changes) in the remarks section."""
        config = self.mapping.get('remarks', {})
        x = config.get('x', 80)
        start_y = config.get('start_y', 370)
        line_height = config.get('line_height', 12)
        max_lines = config.get('max_lines', 6)
        font = config.get('font', 'Helvetica')
        size = config.get('size', 8)

        c.setFont(font, size)
        c.setFillColor(black)

        for i, remark in enumerate(remarks[:max_lines]):
            y = start_y - (i * line_height)
            c.drawString(x, y, remark)

    def _draw_recap(
        self,
        c: canvas.Canvas,
        on_duty_today: float,
        total_hours_7days: float,
        total_hours_8days: float,
        cycle_type: str = "70_8",
    ):
        """Draw the 70hr/8day and 60hr/7day recap section."""
        c.setFont('Helvetica', 8)
        c.setFillColor(black)

        recap_70 = self.mapping.get('recap_70hr', {})
        recap_60 = self.mapping.get('recap_60hr', {})

        # On-duty hours today
        if 'on_duty_today' in recap_70:
            pos = recap_70['on_duty_today']
            c.drawCentredString(pos['x'], pos['y'], f"{on_duty_today:.1f}")

        # 70hr/8day section
        if 'total_hours_8days' in recap_60:
            pos = recap_60['total_hours_8days']
            c.drawCentredString(pos['x'], pos['y'], f"{total_hours_8days:.1f}")

        available_70 = max(0, 70 - total_hours_8days)
        if 'available_tomorrow' in recap_60:
            pos = recap_60['available_tomorrow']
            c.drawCentredString(pos['x'], pos['y'], f"{available_70:.1f}")

        # 60hr/7day section
        if 'total_hours_7days' in recap_70:
            pos = recap_70['total_hours_7days']
            c.drawCentredString(pos['x'], pos['y'], f"{total_hours_7days:.1f}")

        available_60 = max(0, 60 - total_hours_7days)
        if 'available_tomorrow' in recap_70:
            pos = recap_70['available_tomorrow']
            c.drawCentredString(pos['x'], pos['y'], f"{available_60:.1f}")

    def generate_single_day(
        self,
        log_date: date,
        entries: list[dict],
        driver_info: dict,
        daily_totals: dict,
        remarks: list[str],
        historical_hours_7day: float = 0.0,
        historical_hours_8day: float = 0.0,
    ) -> bytes:
        """
        Generate a single-day RODS PDF page.

        Args:
            log_date: The date for this log
            entries: List of duty status entries for this day
                     Each: {status, start_time, end_time, location, remarks}
            driver_info: Dict with carrier_name, carrier_address, home_terminal,
                        vehicle_numbers, shipping_doc, shipper_commodity
            daily_totals: Dict with off_duty_hours, sleeper_hours, driving_hours, on_duty_hours
            remarks: List of remark strings (location changes)
            historical_hours_7day: Total on-duty hours in last 7 days
            historical_hours_8day: Total on-duty hours in last 8 days

        Returns:
            PDF bytes of the completed RODS page
        """
        # Create overlay canvas
        overlay_buffer = io.BytesIO()
        page_width = self.mapping.get('page_size', {}).get('width', 612)
        page_height = self.mapping.get('page_size', {}).get('height', 792)
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))


        # Determine from/to locations
        from_loc = ""
        to_loc = ""
        if entries:
            for e in entries:
                loc = e.get('location', '')
                if loc and not from_loc:
                    from_loc = loc
                if loc:
                    to_loc = loc

        # Draw all elements
        on_duty_today = daily_totals.get('driving_hours', 0) + daily_totals.get('on_duty_hours', 0)

        self._draw_header_fields(
            c,
            log_date=log_date,
            from_location=from_loc,
            to_location=to_loc,
            carrier_name=driver_info.get('carrier_name', ''),
            main_office_address=driver_info.get('carrier_address', ''),
            home_terminal_address=driver_info.get('home_terminal', ''),
            total_miles_driving=daily_totals.get('total_miles', 0),
            total_mileage=daily_totals.get('total_mileage', 0),
            vehicle_numbers=driver_info.get('vehicle_numbers', ''),
            shipping_doc=driver_info.get('shipping_doc', ''),
            shipper_commodity=driver_info.get('shipper_commodity', ''),
        )

        self._draw_graph_grid(c, entries)

        self._draw_total_hours(
            c,
            off_duty_hours=daily_totals.get('off_duty_hours', 0),
            sleeper_hours=daily_totals.get('sleeper_hours', 0),
            driving_hours=daily_totals.get('driving_hours', 0),
            on_duty_hours=daily_totals.get('on_duty_hours', 0),
        )

        self._draw_remarks(c, remarks)

        self._draw_recap(
            c,
            on_duty_today=on_duty_today,
            total_hours_7days=historical_hours_7day,
            total_hours_8days=historical_hours_8day,
        )

        c.save()
        overlay_buffer.seek(0)

        # Merge overlay with template
        template_pdf = PdfReader(self.template_path)
        overlay_pdf = PdfReader(overlay_buffer)

        writer = PdfWriter()
        template_page = template_pdf.pages[0]
        overlay_page = overlay_pdf.pages[0]
        template_page.merge_page(overlay_page)
        writer.add_page(template_page)

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    def generate_trip_pdf(
        self,
        daily_summaries: list[dict],
        driver_info: dict,
        historical_hours_7day: float = 0.0,
        historical_hours_8day: float = 0.0,
    ) -> bytes:
        """
        Generate a multi-day RODS PDF for a complete trip.

        Each day gets its own page, all merged into one PDF.
        """
        writer = PdfWriter()

        for day_summary in daily_summaries:
            log_date = day_summary.get('date')
            if isinstance(log_date, str):
                log_date = date.fromisoformat(log_date)

            entries = day_summary.get('entries', [])

            daily_totals = {
                'driving_hours': day_summary.get('driving_hours', 0),
                'on_duty_hours': day_summary.get('on_duty_hours', 0),
                'off_duty_hours': day_summary.get('off_duty_hours', 0),
                'sleeper_hours': day_summary.get('sleeper_hours', 0),
                'total_miles': day_summary.get('total_miles', 0),
                'total_mileage': day_summary.get('total_mileage', 0),
            }

            # Extract remarks from entries
            remarks = []
            for e in entries:
                loc = e.get('location', '')
                rmk = e.get('remarks', '')
                if loc:
                    status_label = e.get('status', '').replace('_', ' ').title()
                    remarks.append(f"{loc} - {rmk}" if rmk else loc)

            day_pdf_bytes = self.generate_single_day(
                log_date=log_date,
                entries=entries,
                driver_info=driver_info,
                daily_totals=daily_totals,
                remarks=remarks,
                historical_hours_7day=historical_hours_7day,
                historical_hours_8day=historical_hours_8day,
            )

            # Add each day's page to the final document
            day_reader = PdfReader(io.BytesIO(day_pdf_bytes))
            for page in day_reader.pages:
                writer.add_page(page)

            # Update rolling hours for next day
            on_duty = daily_totals['driving_hours'] + daily_totals['on_duty_hours']
            historical_hours_7day += on_duty
            historical_hours_8day += on_duty

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()


def generate_trip_pdf(trip) -> bytes:
    """
    Bridge function that accepts a Trip model instance and generates the RODS PDF.

    This is the entry point called by the views. It:
      1. Fetches duty logs for the trip
      2. Groups them by date into daily summaries
      3. Passes them to the RODSPDFGenerator
    """
    from collections import defaultdict
    from apps.hos.models import DutyStatusLog

    generator = RODSPDFGenerator()

    # Fetch duty logs for this trip
    logs = DutyStatusLog.objects.filter(trip=trip).order_by('start_time')

    # Group entries by date, splitting cross-midnight entries
    days_map = defaultdict(list)
    for log in logs:
        start = log.start_time
        end = log.end_time
        entry = {
            'status': log.status,
            'start_time': start,
            'end_time': end,
            'location': log.location_name or '',
            'remarks': log.remarks or '',
        }

        if end and start.date() != end.date():
            # Entry crosses midnight - split into per-day segments
            from django.utils import timezone as tz
            current_day = start.date()
            while current_day <= end.date():
                if current_day == start.date():
                    day_end = tz.make_aware(datetime.combine(current_day + timedelta(days=1), datetime.min.time())) if tz.is_aware(start) else datetime.combine(current_day + timedelta(days=1), datetime.min.time())
                    days_map[current_day].append({**entry, 'end_time': day_end})
                elif current_day == end.date():
                    day_start = tz.make_aware(datetime.combine(current_day, datetime.min.time())) if tz.is_aware(end) else datetime.combine(current_day, datetime.min.time())
                    days_map[current_day].append({**entry, 'start_time': day_start})
                else:
                    day_start = tz.make_aware(datetime.combine(current_day, datetime.min.time())) if tz.is_aware(start) else datetime.combine(current_day, datetime.min.time())
                    day_end = tz.make_aware(datetime.combine(current_day + timedelta(days=1), datetime.min.time())) if tz.is_aware(start) else datetime.combine(current_day + timedelta(days=1), datetime.min.time())
                    days_map[current_day].append({**entry, 'start_time': day_start, 'end_time': day_end})
                current_day += timedelta(days=1)
        else:
            days_map[start.date()].append(entry)

    # Build daily summaries
    daily_summaries = []
    for day_date in sorted(days_map.keys()):
        entries = days_map[day_date]
        driving_hours = 0.0
        on_duty_hours = 0.0
        off_duty_hours = 0.0
        sleeper_hours = 0.0

        for e in entries:
            if e['end_time'] and e['start_time']:
                hours = (e['end_time'] - e['start_time']).total_seconds() / 3600
            else:
                hours = 0.0

            if e['status'] == 'driving':
                driving_hours += hours
            elif e['status'] == 'on_duty_not_driving':
                on_duty_hours += hours
            elif e['status'] == 'off_duty':
                off_duty_hours += hours
            elif e['status'] == 'sleeper_berth':
                sleeper_hours += hours

        # Skip days with only off-duty/sleeper time (no work activity)
        if driving_hours == 0 and on_duty_hours == 0:
            continue

        daily_summaries.append({
            'date': day_date,
            'entries': entries,
            'driving_hours': round(driving_hours, 1),
            'on_duty_hours': round(on_duty_hours, 1),
            'off_duty_hours': round(off_duty_hours, 1),
            'sleeper_hours': round(sleeper_hours, 1),
            'total_miles': float(trip.total_distance_miles or 0) / max(len(days_map), 1),
            'total_mileage': float(trip.total_distance_miles or 0),
        })

    # Build driver info
    driver = trip.driver
    driver_info = {
        'carrier_name': getattr(driver, 'carrier_name', '') or '',
        'carrier_address': getattr(driver, 'carrier_address', '') or '',
        'home_terminal': getattr(driver, 'home_terminal_address', '') or '',
        'vehicle_numbers': getattr(driver, 'truck_number', '') or '',
        'shipping_doc': '',
        'shipper_commodity': '',
    }

    if not daily_summaries:
        # No logs yet - return a placeholder
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas as canvas_mod
        buf = io.BytesIO()
        c = canvas_mod.Canvas(buf, pagesize=letter)
        c.setFont('Helvetica-Bold', 14)
        c.drawString(72, 700, f'Trip #{trip.id} - No duty logs available')
        c.setFont('Helvetica', 11)
        c.drawString(72, 670, f'{trip.current_location} -> {trip.pickup_location} -> {trip.dropoff_location}')
        c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()

    return generator.generate_trip_pdf(
        daily_summaries=daily_summaries,
        driver_info=driver_info,
    )
