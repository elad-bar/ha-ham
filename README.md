<h1>HAM (Home Assistant Manager)</h1>
<h2>Description</h2>
Provides management layer above the Home Assistant to apply different scenes according to the needs,
Instructions are in the example below.

<h2>Example</h2>
<pre>
configuration: 
    ham:
      #Required
      default_profile:
        #Required - List of day parts objects
        parts:
          #Day part contains:
          # name - string, can be one, few or all from the following list:
          #         Morning, Noon, Afternoon, Evening, Night
          # from - time - HH:mm:SS
          - name: Morning
            from: '06:00:00'
          - name: Noon
            from: '12:00:00'
          - name: Afternoon
            from: '16:00:00'
          - name: Evening
            from: '20:00:00'
          - name: Night
            from: '23:00:00'
    
      trackers:                   #Optional - List of entity ids represents device_tracker components
        - device_tracker.device_name
    
    
      #In the example below different scenes for each day part and away scene,
      #Each of the scene will invoke the script once it will be activated
    
      scenes:                     #Optional - List of scene objects
        - scene: Morning          #Required - Represent the scene name
          script:                 #Required - Represent script object (HA Script)
            - service: notify.world
              data:
                message: 'Good morning'
        - scene: Noon
          script:
            - service: notify.world
              data:
                message: 'Time to rest'
        - scene: Afternoon
          script:
            - service: notify.world
              data:
                message: 'It is afternoon'
        - scene: Evening
          script:
            - service: notify.world
              data:
                message: 'Get the kids to bed'
        - scene: Night
          script:
            - service: notify.world
              data:
                message: 'Good night'
        - scene: Away
          script:
            - service: notify.world
              data:
                message: 'Home alone'
    
      #In the example below there are 2 additional profiles: HalfDay and Holiday
      #Each of the profiles will override the default profile defintions of day parts
      #It's not required to override all day parts, you can override just one of then if needed
      #Profile overrides will take place only when events are defined (section below)
    
      profiles:                   #Optional - List of profile objects
        - profile: HalfDay        #Required - Represent the profile name
          parts:                  #Required - List of day parts objects (description on day part object above)
            - name: Morning
              from: '06:30:00'
            - name: Noon
              from: '12:30:00'
            - name: Afternoon
              from: '16:30:00'
            - name: Evening
              from: '21:30:00'
            - name: Night
              from: '23:00:00'
        - profile: Holiday
          parts:
            - name: Morning
              from: '09:00:00'
            - name: Noon
              from: '12:30:00'
            - name: Afternoon
              from: '16:30:00'
            - name: Evening
              from: '20:00:00'
            - name: Night
              from: '23:00:00'
    
      #In the example below there are 3 events:
      #   Reoccouring every Friday - HalfDay profile overrides, Named Weekend Evening
      #   Reoccouring every Saturday - Holiday profile overrides, Named Weekend
      #   At Jan 1st 2019 - Holiday profile overrides, Named New Year
    
      events:                     #Optional - List of event objects, there are 2 event object types - Day / Date based
        #Day based
        - profile: HalfDay        #Required - Represent the profile name
          day: Friday             #Required - Day of the week, can be one of: Sunday, Monday, Tuesday, Wednesday, Thursday, Friday, Saturday
          title: Weekend Evening  #Required - Title to display
        #Day based
        - profile: Holiday
          day: Saturday
          title: Weekend
        #Date based
        - profile: Holiday        #Required - Represent the profile name
          date: '2019-01-01'      #Required - Date formatted as YYYY-mm-DD
          title: 'New year'       #Required - Title to display
    
    #Once binary sensor defined, for each profile (default and overrides) will be created a component
    #Name of the sensor will be the profile name
    #State of the binary sensor will be based on the fact whether it's activated or not
    #Attributes are the day parts related to it
    
    binary_sensor:
      - platform: ham
    
    #Once sensor defined, 4 sensor will be added:
    #   1. Weekday - state will represent the day name
    #   2. Current Day Part - state will represent the current day part
    #   3. Current Profile - state will represent the current profile name
    #                        Attributes of that sensor will present the same attributes of the binary sensor attributes of the current profile
    #   4. Current Scene - state will represent the current profile name or away mode in case none of the device tracker are at home,
    #                      when that sensor state is being changed it triggers the different scripts of the corresponding scene
    
    sensor:
      - platform: ham
</pre> 

<h2>Custom_updater</h2>
<pre>
custom_updater:
  track:
    - components
  component_urls:
    - https://raw.githubusercontent.com/elad-bar/ha-ham/master/ham.json
</pre>
